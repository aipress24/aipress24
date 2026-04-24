# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Tests for the PR publication notification helper."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest

from app.models.auth import User
from app.models.organisation import Organisation
from app.modules.bw.bw_activation.models import (
    BusinessWall,
    BWStatus,
    Partnership,
    PartnershipStatus,
)
from app.modules.wip.services.pr_notifications import (
    notify_client_of_pr_publication,
)

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


def _mk_user_org_bw(
    db_session: Session, name: str, bw_type: str = "media"
) -> tuple[User, Organisation, BusinessWall]:
    unique = uuid.uuid4().hex[:6]
    user = User(
        email=f"{name.lower()}-{unique}@example.com",
        first_name=name,
        last_name="T",
        active=True,
    )
    db_session.add(user)
    db_session.flush()

    org = Organisation(name=f"{name} Org {unique}")
    db_session.add(org)
    db_session.flush()
    user.organisation = org
    user.organisation_id = org.id

    bw = BusinessWall(
        bw_type=bw_type,
        status=BWStatus.ACTIVE.value,
        is_free=True,
        owner_id=user.id,
        payer_id=user.id,
        organisation_id=org.id,
    )
    db_session.add(bw)
    db_session.flush()
    org.bw_id = bw.id
    org.bw_active = bw_type
    org.bw_name = org.name
    db_session.flush()
    return user, org, bw


def _add_partnership(
    db_session: Session,
    client_bw: BusinessWall,
    agency_bw: BusinessWall,
    status: PartnershipStatus = PartnershipStatus.ACTIVE,
) -> Partnership:
    p = Partnership(
        business_wall_id=client_bw.id,
        partner_bw_id=str(agency_bw.id),
        status=status.value,
        invited_by_user_id=client_bw.owner_id,
        invited_at=datetime.now(UTC),
    )
    db_session.add(p)
    db_session.flush()
    return p


@pytest.fixture
def agency_and_client(db_session: Session):
    agency_user, _, agency_bw = _mk_user_org_bw(db_session, "Agency", "pr")
    client_owner, client_org, client_bw = _mk_user_org_bw(db_session, "Client", "media")
    _add_partnership(db_session, client_bw, agency_bw)
    return agency_user, client_owner, client_org


class TestNotifyClientOfPrPublication:
    def test_sends_email_when_agency_publishes_for_client(
        self, db_session: Session, agency_and_client
    ):
        agency_user, _, client_org = agency_and_client

        with patch(
            "app.services.emails.PRPublicationNotificationMail.send"
        ) as mock_send:
            notify_client_of_pr_publication(
                author=agency_user,
                client_org=client_org,
                content_type="communiqué",
                content_title="Lancement X",
                content_url="https://aipress24.com/wire/42",
            )

        mock_send.assert_called_once()

    def test_skips_when_author_is_in_same_org(
        self, db_session: Session, agency_and_client
    ):
        """No 'PR agency' scenario → no notification."""
        _, client_owner, client_org = agency_and_client

        with patch(
            "app.services.emails.PRPublicationNotificationMail.send"
        ) as mock_send:
            notify_client_of_pr_publication(
                author=client_owner,
                client_org=client_org,
                content_type="communiqué",
                content_title="Auto-publication",
                content_url="https://example.com",
            )

        mock_send.assert_not_called()

    def test_skips_when_no_reachable_recipient(self, db_session: Session):
        agency_user, _, _ = _mk_user_org_bw(db_session, "Agency", "pr")

        orphan_org = Organisation(name=f"Orphan-{uuid.uuid4().hex[:6]}")
        db_session.add(orphan_org)
        db_session.flush()

        with patch(
            "app.services.emails.PRPublicationNotificationMail.send"
        ) as mock_send:
            notify_client_of_pr_publication(
                author=agency_user,
                client_org=orphan_org,
                content_type="communiqué",
                content_title="Nope",
                content_url="https://example.com",
            )

        mock_send.assert_not_called()

    def test_mail_payload_contains_agency_and_client_names(
        self, db_session: Session, agency_and_client
    ):
        agency_user, _, client_org = agency_and_client

        captured = {}

        def _fake_send(self):
            captured.update(
                {
                    "recipient": self.recipient,
                    "agency_name": self.agency_name,
                    "client_name": self.client_name,
                    "content_type": self.content_type,
                    "content_title": self.content_title,
                }
            )
            return True

        with patch(
            "app.services.emails.PRPublicationNotificationMail.send",
            autospec=True,
            side_effect=_fake_send,
        ):
            notify_client_of_pr_publication(
                author=agency_user,
                client_org=client_org,
                content_type="communiqué",
                content_title="Titre test",
                content_url="https://example.com/42",
            )

        assert captured["agency_name"] == agency_user.organisation.bw_name
        assert captured["client_name"] == client_org.bw_name
        assert captured["content_type"] == "communiqué"
        assert captured["content_title"] == "Titre test"
