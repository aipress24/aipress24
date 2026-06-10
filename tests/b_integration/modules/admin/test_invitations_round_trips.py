# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Round-trip integration tests for ``app.modules.admin.invitations``.

The existing ``test_invitations.py`` in this directory exercises the higher
level ``invite_users`` flow (which also drives mail / notification
side-effects). This file covers the gap: the underlying ``add_invited_users``
function, which is the pure DB-touching primitive. We assert on its return
value AND on the resulting ``Invitation`` rows so that we pin down:

* the normalisation contract introduced by bug #0130 (trimmed + lowercased),
* the idempotency contract (a second call returns ``[]`` and creates no row),
* the row shape after persistence (``id``, ``created_at``, ``organisation_id``),
* cross-organisation isolation, and
* the absence of a hard FK on ``organisation_id`` (documents current schema).

Lives at the ``b_integration`` tier because it uses the real SQLAlchemy
session via the autouse ``db_session`` fixture; nothing here is pure logic.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from app.models.invitation import Invitation
from app.models.organisation import Organisation
from app.modules.admin.invitations import (
    add_invited_users,
    emails_invited_to_organisation,
)

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


@pytest.fixture
def org(db_session: Session) -> Organisation:
    """A persisted organisation usable as an invitation target."""
    organisation = Organisation(name="Round-Trip Org")
    db_session.add(organisation)
    db_session.flush()
    return organisation


class TestAddInvitedUsersReturnValue:
    """``add_invited_users`` returns exactly the newly-stored, normalised mails."""

    def test_returns_normalised_single_email(
        self, db_session: Session, org: Organisation
    ) -> None:
        added = add_invited_users("  Alice@Example.COM  ", org.id)

        assert added == ["alice@example.com"]
        stored = db_session.query(Invitation).one()
        assert stored.email == "alice@example.com"
        assert stored.organisation_id == org.id

    def test_returns_only_new_mails_on_second_call(
        self, db_session: Session, org: Organisation
    ) -> None:
        first = add_invited_users(["a@x.io", "b@x.io"], org.id)
        second = add_invited_users(["a@x.io", "c@x.io"], org.id)

        assert first == ["a@x.io", "b@x.io"]
        assert second == ["c@x.io"]
        assert db_session.query(Invitation).count() == 3

    def test_returns_empty_when_no_valid_input(
        self, db_session: Session, org: Organisation
    ) -> None:
        added = add_invited_users(["", "no-at-sign", "   "], org.id)

        assert added == []
        assert db_session.query(Invitation).count() == 0

    def test_returns_empty_when_input_is_empty_list(
        self, db_session: Session, org: Organisation
    ) -> None:
        added = add_invited_users([], org.id)

        assert added == []
        assert db_session.query(Invitation).count() == 0

    def test_preserves_input_order_in_return_value(
        self, db_session: Session, org: Organisation
    ) -> None:
        mails = ["zeta@x.io", "alpha@x.io", "mike@x.io"]

        added = add_invited_users(mails, org.id)

        # Return order should mirror input order, NOT sort it.
        assert added == mails


class TestAddInvitedUsersIdempotency:
    """Repeated invitations of the same address do not duplicate rows."""

    @pytest.mark.parametrize(
        "second_variant",
        [
            "user@example.com",
            "USER@example.com",
            "  user@example.com  ",
            "User@Example.Com",
        ],
    )
    def test_second_call_with_same_logical_email_is_no_op(
        self,
        db_session: Session,
        org: Organisation,
        second_variant: str,
    ) -> None:
        add_invited_users("user@example.com", org.id)
        added_second = add_invited_users(second_variant, org.id)

        assert added_second == []
        rows = db_session.query(Invitation).all()
        assert len(rows) == 1
        assert rows[0].email == "user@example.com"

    def test_duplicates_within_one_call_collapse(
        self, db_session: Session, org: Organisation
    ) -> None:
        added = add_invited_users(
            ["dup@x.io", "DUP@x.io", " dup@x.io "],
            org.id,
        )

        assert added == ["dup@x.io"]
        assert db_session.query(Invitation).count() == 1


class TestInvitationRowShape:
    """Persisted ``Invitation`` rows must expose the expected fields."""

    def test_row_has_id_and_timestamps_after_flush(
        self, db_session: Session, org: Organisation
    ) -> None:
        add_invited_users("shape@example.com", org.id)

        row = db_session.query(Invitation).one()
        assert row.id is not None
        assert row.created_at is not None  # set by LifeCycleMixin before_insert
        assert row.email == "shape@example.com"
        assert row.organisation_id == org.id

    def test_query_back_by_organisation_id(
        self, db_session: Session, org: Organisation
    ) -> None:
        add_invited_users(["a@x.io", "b@x.io"], org.id)

        rows = (
            db_session.query(Invitation)
            .filter(Invitation.organisation_id == org.id)
            .all()
        )
        assert {r.email for r in rows} == {"a@x.io", "b@x.io"}


class TestCrossOrganisationIsolation:
    """Each organisation has its own invitation namespace."""

    def test_same_email_can_be_invited_to_two_orgs(self, db_session: Session) -> None:
        org_a = Organisation(name="Org A")
        org_b = Organisation(name="Org B")
        db_session.add_all([org_a, org_b])
        db_session.flush()

        added_a = add_invited_users("dual@x.io", org_a.id)
        added_b = add_invited_users("dual@x.io", org_b.id)

        assert added_a == ["dual@x.io"]
        assert added_b == ["dual@x.io"]
        assert emails_invited_to_organisation(org_a.id) == ["dual@x.io"]
        assert emails_invited_to_organisation(org_b.id) == ["dual@x.io"]
        assert db_session.query(Invitation).count() == 2

    def test_one_org_invitation_does_not_block_another(
        self, db_session: Session
    ) -> None:
        org_a = Organisation(name="Org A")
        org_b = Organisation(name="Org B")
        db_session.add_all([org_a, org_b])
        db_session.flush()

        add_invited_users(["a@x.io", "b@x.io"], org_a.id)
        added_b = add_invited_users(["b@x.io", "c@x.io"], org_b.id)

        assert added_b == ["b@x.io", "c@x.io"]
        assert emails_invited_to_organisation(org_a.id) == ["a@x.io", "b@x.io"]
        assert emails_invited_to_organisation(org_b.id) == ["b@x.io", "c@x.io"]


class TestOrganisationIdReferenceBehavior:
    """The ``organisation_id`` column has no FK constraint at the schema level.

    Documenting current behaviour: passing an org id that does not exist still
    succeeds. If a hard FK is added later this test will catch the change.
    """

    def test_unknown_org_id_still_creates_row(self, db_session: Session) -> None:
        nonexistent_id = 99_999_999

        added = add_invited_users("orphan@x.io", nonexistent_id)

        assert added == ["orphan@x.io"]
        row = db_session.query(Invitation).one()
        assert row.organisation_id == nonexistent_id


class TestInputVariants:
    """``add_invited_users`` accepts ``str`` or ``list[str]`` interchangeably."""

    @pytest.mark.parametrize(
        ("payload", "expected_emails"),
        [
            ("solo@x.io", ["solo@x.io"]),
            (["solo@x.io"], ["solo@x.io"]),
            (["a@x.io", "b@x.io"], ["a@x.io", "b@x.io"]),
        ],
    )
    def test_accepts_str_or_list(
        self,
        db_session: Session,
        org: Organisation,
        payload: str | list[str],
        expected_emails: list[str],
    ) -> None:
        added = add_invited_users(payload, org.id)

        assert added == expected_emails
        stored = sorted(r.email for r in db_session.query(Invitation).all())
        assert stored == sorted(expected_emails)
