# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Unit tests for `wip/services/pr_notifications.py`.

Drives the early-return / fallback branches that don't require
the full e2e partnership setup of CM-2.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import TYPE_CHECKING
from unittest.mock import patch

from app.models.auth import User
from app.models.organisation import Organisation
from app.modules.wip.services.pr_notifications import (
    _pick_bw_owner_email,
    notify_client_of_pr_publication,
)

if TYPE_CHECKING:
    from flask_sqlalchemy import SQLAlchemy


def _mk_user(db: SQLAlchemy, *, email: str, organisation_id: int | None = None) -> User:
    user = User(
        email=email,
        first_name="X",
        last_name="Y",
        active=True,
        organisation_id=organisation_id,
    )
    db.session.add(user)
    db.session.flush()
    return user


class TestNotifyClientOfPRPublication:
    """Cover the early-return / no-recipient branches."""

    def test_skipped_when_author_same_org_as_client(self, db: SQLAlchemy) -> None:
        """No mail sent when author belongs to the client org
        (it's a self-publication, not a PR-agency-on-behalf
        scenario)."""
        org = Organisation(name="Same Org")
        db.session.add(org)
        db.session.flush()
        author = _mk_user(
            db,
            email="self@example.com",
            organisation_id=org.id,
        )
        with patch(
            "app.modules.wip.services.pr_notifications.PRPublicationNotificationMail"
        ) as mail_cls:
            notify_client_of_pr_publication(
                author=author,
                client_org=org,
                content_type="Article",
                content_title="t",
                content_url="/wire/x",
            )
        mail_cls.assert_not_called()

    def test_skipped_when_no_owner_email_resolvable(self, db: SQLAlchemy) -> None:
        """`_pick_bw_owner_email` returns "" → no mail sent."""
        author_org = Organisation(name="Author Org")
        client_org = Organisation(name="Client Org with no member")
        db.session.add_all([author_org, client_org])
        db.session.flush()
        author = _mk_user(
            db,
            email="author@example.com",
            organisation_id=author_org.id,
        )
        # client_org has no members and no BW → resolver returns "".
        with patch(
            "app.modules.wip.services.pr_notifications.PRPublicationNotificationMail"
        ) as mail_cls:
            notify_client_of_pr_publication(
                author=author,
                client_org=client_org,
                content_type="Article",
                content_title="t",
                content_url="/wire/x",
            )
        mail_cls.assert_not_called()


class TestPickBwOwnerEmail:
    """Cover `_pick_bw_owner_email` resolver branches."""

    def test_returns_empty_string_when_no_bw_no_members(self, db: SQLAlchemy) -> None:
        """Org without BW and without members → returns ""."""
        org = Organisation(name="Empty Org")
        db.session.add(org)
        db.session.flush()
        assert _pick_bw_owner_email(org) == ""

    def test_falls_back_to_first_active_member_when_no_bw(self, db: SQLAlchemy) -> None:
        """No BW → fallback to first active member's email."""
        org = Organisation(name="Org No BW")
        db.session.add(org)
        db.session.flush()
        member = _mk_user(
            db,
            email="member@example.com",
            organisation_id=org.id,
        )
        with patch(
            "app.modules.bw.bw_activation.user_utils."
            "get_active_business_wall_for_organisation",
            return_value=None,
        ):
            assert _pick_bw_owner_email(org) == member.email

    def test_skips_inactive_members_in_fallback(self, db: SQLAlchemy) -> None:
        """Inactive members are skipped — returns "" if no active
        ones exist."""
        org = Organisation(name="Org Inactive Members")
        db.session.add(org)
        db.session.flush()
        # An inactive member doesn't qualify.
        inactive = User(
            email="inactive@example.com",
            first_name="X",
            last_name="Y",
            active=False,
            organisation_id=org.id,
        )
        db.session.add(inactive)
        db.session.flush()
        with patch(
            "app.modules.bw.bw_activation.user_utils."
            "get_active_business_wall_for_organisation",
            return_value=None,
        ):
            assert _pick_bw_owner_email(org) == ""

    def test_returns_bw_owner_email_when_resolvable(self, db: SQLAlchemy) -> None:
        """When the BW has an owner with an email, return that
        email (preferred path)."""
        org = Organisation(name="Org With BW")
        db.session.add(org)
        db.session.flush()
        owner = _mk_user(
            db,
            email="bw-owner@example.com",
            organisation_id=org.id,
        )
        bw_stub = SimpleNamespace(owner_id=owner.id)
        with patch(
            "app.modules.bw.bw_activation.user_utils."
            "get_active_business_wall_for_organisation",
            return_value=bw_stub,
        ):
            assert _pick_bw_owner_email(org) == owner.email
