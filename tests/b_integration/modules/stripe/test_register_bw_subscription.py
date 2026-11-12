# Copyright (c) 2021-2026, Abilian SAS & TCA
# SPDX-License-Identifier: AGPL-3.0-only

"""Integration tests for `_register_bw_subscription` in
`app.modules.stripe.views.webhook`.

Every subscription-lifecycle handler (`customer.subscription.created`,
`updated`, `paused`, `resumed`, ...) funnels into it. It finds the
Business Wall the subscription was bought for, from the `Subscription`
row checkout linked or from the `bw_id` our checkout put in metadata,
and mirrors the subscription onto that wall's organisation. The payer's
email plays no part: whoever pays types it in at Stripe.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

import pytest
from sqlalchemy import delete, select

from app.enums import BWStatus
from app.models.auth import User
from app.models.organisation import Organisation
from app.modules.bw.bw_activation.models import BusinessWall, Subscription
from app.modules.stripe.views.webhook import (
    SubscriptionInfo,
    _register_bw_subscription,
)

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


def _org_with_bw(db_session: Session) -> tuple[User, Organisation, BusinessWall]:
    suffix = uuid.uuid4().hex[:8]
    org = Organisation(name=f"Stripe Test Org {suffix}", bw_active="", active=False)
    db_session.add(org)
    db_session.flush()
    owner = User(email=f"stripe-sub-{suffix}@example.com", active=True)
    owner.organisation = org
    db_session.add(owner)
    db_session.flush()
    bw = BusinessWall(
        bw_type="media",
        status=BWStatus.ACTIVE.value,
        is_free=False,
        owner_id=owner.id,
        payer_id=owner.id,
        organisation_id=org.id,
    )
    db_session.add(bw)
    db_session.flush()
    return owner, org, bw


def _subinfo(
    *,
    customer_email: str = "anyone@example.com",
    subscription_id: str = "sub_unlinked",
    bw_id: str = "",
    status: bool = True,
) -> SubscriptionInfo:
    """Build the value object without the Stripe SDK calls of
    `_make_customer_subscription_info`."""
    s = SubscriptionInfo()
    s.customer_email = customer_email
    s.subscription_id = subscription_id
    s.client_reference_id = bw_id
    s.bw_type = "leaders_experts"
    s.status = status
    s.operation = "update"
    s.name = "Test Plan"
    s.quantity = 1
    return s


def test_a_linked_subscription_updates_its_wall_organisation(
    db_session: Session,
) -> None:
    _owner, org, bw = _org_with_bw(db_session)
    sub_id = f"sub_{uuid.uuid4().hex[:8]}"
    db_session.add(
        Subscription(
            business_wall_id=bw.id,
            stripe_subscription_id=sub_id,
            pricing_field="stripe",
            pricing_tier="via_pricing_table",
            monthly_price=0,
            annual_price=0,
        )
    )
    db_session.flush()

    _register_bw_subscription(_subinfo(subscription_id=sub_id))

    db_session.refresh(org)
    assert org.bw_active == "leaders_experts"
    assert org.active is True


def test_metadata_bw_id_is_the_fallback(db_session: Session) -> None:
    _owner, org, bw = _org_with_bw(db_session)

    _register_bw_subscription(_subinfo(bw_id=str(bw.id), status=False))

    db_session.refresh(org)
    assert org.bw_active == "leaders_experts"
    assert org.active is False


def test_the_payer_email_selects_nothing(db_session: Session) -> None:
    """A payer typing a member's email does not reach that member's org."""
    member, org, _bw = _org_with_bw(db_session)

    _register_bw_subscription(_subinfo(customer_email=member.email))

    db_session.refresh(org)
    assert org.bw_active == ""
    assert org.active is False


def test_none_subinfo_is_noop(db_session: Session) -> None:
    """`_make_customer_subscription_info` returns None when Stripe
    cannot be reached."""
    _register_bw_subscription(None)


@pytest.fixture(autouse=True)
def _purge_committed_rows(db_session: Session):
    """`_register_bw_subscription` commits, so the savepoint cannot roll
    these rows back."""
    yield
    users = db_session.scalars(
        select(User).where(User.email.like("stripe-sub-%"))
    ).all()
    org_ids = [u.organisation_id for u in users]
    bw_ids = db_session.scalars(
        select(BusinessWall.id).where(BusinessWall.organisation_id.in_(org_ids))
    ).all()
    db_session.execute(
        delete(Subscription).where(Subscription.business_wall_id.in_(bw_ids))
    )
    db_session.execute(delete(BusinessWall).where(BusinessWall.id.in_(bw_ids)))
    db_session.execute(delete(User).where(User.id.in_([u.id for u in users])))
    db_session.execute(delete(Organisation).where(Organisation.id.in_(org_ids)))
    db_session.commit()
