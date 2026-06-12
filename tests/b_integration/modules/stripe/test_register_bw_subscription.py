# Copyright (c) 2021-2026, Abilian SAS & TCA
# SPDX-License-Identifier: AGPL-3.0-only

"""Integration tests for `_register_bw_subscription` in
`app.modules.stripe.views.webhook`.

This is the orchestrator every subscription-lifecycle webhook handler
funnels into : `customer.subscription.created`, `updated`, `deleted`,
`paused`, `resumed`, `trial_will_end`, `pending_update_applied`,
`pending_update_expired`. The handlers differ only in the `operation`
label they tag the `SubscriptionInfo` with ; the actual « find user,
verify org, update org.bw_active + org.active, ack » work all happens
in `_register_bw_subscription`.

Pinning the orchestrator's decision paths at b_integration :

* user lookup by email ; missing user → silent skip (no mutation).
* user has no organisation → silent skip.
* `subinfo.client_reference_id` exists but doesn't match `org.id` →
  silent skip (security boundary — Stripe metadata says BW belongs
  to a different org).
* happy path → `org.bw_active` flips to `subinfo.bw_type`,
  `org.active` flips to `subinfo.status` (bool).

Pure helpers (`extract_subscription_period`, `extract_subscription_plan`,
`should_apply_subscription_to_org`) are covered separately at a_unit
in `tests/a_unit/modules/stripe/test_subscription_payload_helpers.py`.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

import pytest
from sqlalchemy import or_, select

from app.models.auth import User
from app.models.invitation import Invitation
from app.models.organisation import Organisation
from app.modules.stripe.views.webhook import (
    SubscriptionInfo,
    _register_bw_subscription,
)

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


def _fresh_user_org(
    db_session: Session,
    *,
    email_prefix: str = "stripe-sub",
    org_name_prefix: str = "Stripe Test Org",
) -> tuple[User, Organisation]:
    """Build a paired user + org. Unique email/name per call so several
    can co-exist within the same test (multi-org tests)."""
    suffix = uuid.uuid4().hex[:8]
    org = Organisation(name=f"{org_name_prefix} {suffix}")
    db_session.add(org)
    db_session.flush()

    user = User(
        email=f"{email_prefix}-{suffix}@example.com",
        first_name="Stripe",
        last_name="Tester",
        active=True,
    )
    user.organisation = org
    user.organisation_id = org.id
    db_session.add(user)
    db_session.flush()
    return user, org


def _subinfo(
    *,
    customer_email: str,
    bw_type: str = "media",
    status: bool = True,
    client_reference_id: str = "",
    operation: str = "create",
) -> SubscriptionInfo:
    """Construct a `SubscriptionInfo` value object without going
    through `_make_customer_subscription_info` (which would call into
    the Stripe SDK for customer lookup + product detection).

    The orchestrator reads only `customer_email`, `bw_type`, `status`,
    `client_reference_id`, `operation`, and (for logging) `quantity`
    and `name` — supply the minimum-viable subset."""
    s = SubscriptionInfo()
    s.customer_email = customer_email
    s.bw_type = bw_type
    s.status = status
    s.client_reference_id = client_reference_id
    s.operation = operation
    s.name = "Test Plan"
    s.quantity = 1
    s.subscription_id = "sub_test"
    return s


class TestRegisterBwSubscriptionHappyPath:
    def test_active_subscription_flips_org_bw_active(self, db_session: Session) -> None:
        user, org = _fresh_user_org(db_session)
        org.bw_active = ""
        db_session.flush()

        subinfo = _subinfo(
            customer_email=user.email,
            bw_type="leaders_experts",
            status=True,
            client_reference_id=str(org.id),
        )

        _register_bw_subscription(subinfo)

        db_session.refresh(org)
        assert org.bw_active == "leaders_experts"

    def test_active_subscription_keeps_org_active_true(
        self, db_session: Session
    ) -> None:
        user, org = _fresh_user_org(db_session)
        subinfo = _subinfo(
            customer_email=user.email,
            status=True,
            client_reference_id=str(org.id),
        )

        _register_bw_subscription(subinfo)

        db_session.refresh(org)
        assert org.active is True

    def test_inactive_subscription_deactivates_org(self, db_session: Session) -> None:
        """A subscription in a non-`active` Stripe status (canceled,
        unpaid, past_due) yields `subinfo.status=False` upstream ;
        propagate to the org so the dashboards stop letting them
        publish for the period."""
        user, org = _fresh_user_org(db_session)
        org.active = True
        db_session.flush()

        subinfo = _subinfo(
            customer_email=user.email,
            status=False,
            client_reference_id=str(org.id),
        )

        _register_bw_subscription(subinfo)

        db_session.refresh(org)
        assert org.active is False


class TestRegisterBwSubscriptionGuards:
    def test_none_subinfo_is_noop(self, db_session: Session) -> None:
        """`_make_customer_subscription_info` returns None on Stripe
        customer-fetch failures ; the orchestrator must early-return
        on None (rather than crash on attribute access)."""
        _register_bw_subscription(None)  # type: ignore[arg-type]
        # No assertion required ; absence of exception is the contract.

    def test_unknown_customer_email_is_silent_skip(self, db_session: Session) -> None:
        """No local user matches the Stripe customer's email — bail
        without mutating anything (a user might register tomorrow)."""
        # Build subinfo for an email that doesn't exist locally.
        subinfo = _subinfo(
            customer_email="never-registered@example.com",
            bw_type="leaders_experts",
            status=True,
        )
        # No exception, no mutation — the absence of a target row is
        # the only observable outcome.
        _register_bw_subscription(subinfo)

    def test_user_without_organisation_is_silent_skip(
        self, db_session: Session
    ) -> None:
        """The user exists but has no org attached ; nothing to
        mutate. Pin so a refactor that auto-creates an org from
        Stripe context (bad idea) is conscious."""
        user = User(
            email=f"stripe-noorg-{uuid.uuid4().hex[:8]}@example.com",
            first_name="No",
            last_name="Org",
            active=True,
        )
        db_session.add(user)
        db_session.flush()

        subinfo = _subinfo(customer_email=user.email, bw_type="media", status=True)
        _register_bw_subscription(subinfo)
        # Re-read the user — still no org, no mutation took place.
        db_session.refresh(user)
        assert user.organisation_id is None

    def test_client_reference_id_mismatch_skips_silently(
        self, db_session: Session
    ) -> None:
        """Security boundary : a subscription event whose metadata
        names a different org from the user's must not mutate the
        user's org. Pin the bypass so a refactor that swaps the
        check (or drops it) breaks loudly.

        Set up : user_A in org_A, but the SubscriptionInfo claims
        client_reference_id = org_B (a totally different org).
        Expect : org_A's bw_active stays untouched."""
        user, org_a = _fresh_user_org(db_session, email_prefix="alice")
        _user_b, org_b = _fresh_user_org(db_session, email_prefix="bob")
        org_a.bw_active = "untouched"
        db_session.flush()

        subinfo = _subinfo(
            customer_email=user.email,  # alice (org_a)
            bw_type="media",
            status=True,
            client_reference_id=str(org_b.id),  # but metadata says org_b !
        )

        _register_bw_subscription(subinfo)

        db_session.refresh(org_a)
        assert org_a.bw_active == "untouched"


class TestRegisterBwSubscriptionEmptyReferenceId:
    """Legacy events (pre-`metadata.bw_id` convention) have an empty
    `client_reference_id` — the security check should pass through,
    relying on customer-email matching alone."""

    def test_empty_reference_id_still_applies_to_org(self, db_session: Session) -> None:
        user, org = _fresh_user_org(db_session)
        org.bw_active = ""
        db_session.flush()

        subinfo = _subinfo(
            customer_email=user.email,
            bw_type="leaders_experts",
            status=True,
            client_reference_id="",  # legacy event
        )

        _register_bw_subscription(subinfo)

        db_session.refresh(org)
        assert org.bw_active == "leaders_experts"


# Cleanup : `_register_bw_subscription` commits, so the savepoint can't
# roll the user/org rows back. Also, `add_invited_users(email, org.id)`
# inside the happy path inserts a row in `org_invitations`. Sweep all
# of them by email prefix.
_TEST_EMAIL_PREFIXES = ("stripe-sub-", "stripe-noorg-", "alice-", "bob-")


@pytest.fixture(autouse=True)
def _purge_test_artifacts(db_session: Session):
    yield

    email_filter = or_(*[User.email.like(f"{p}%") for p in _TEST_EMAIL_PREFIXES])
    test_users = db_session.execute(select(User).where(email_filter)).scalars().all()
    if not test_users:
        return

    org_ids = {u.organisation_id for u in test_users if u.organisation_id}
    test_emails = {u.email for u in test_users}

    test_invitations = (
        db_session.execute(select(Invitation).where(Invitation.email.in_(test_emails)))
        .scalars()
        .all()
    )
    for invitation in test_invitations:
        db_session.delete(invitation)

    for u in test_users:
        db_session.delete(u)

    if org_ids:
        for org in (
            db_session.execute(select(Organisation).where(Organisation.id.in_(org_ids)))
            .scalars()
            .all()
        ):
            db_session.delete(org)
    db_session.commit()
