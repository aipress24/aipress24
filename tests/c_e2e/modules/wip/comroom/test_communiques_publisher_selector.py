# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""End-to-end tests for the `publisher_id` selector and notification hook.

Covers the finishing touches from pr-agency-publishing.md §2:
- UI selector populated with own org + validated clients
- Notification e-mail triggered at publish time when publishing for a client
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest

from app.flask.routing import url_for
from app.models.auth import User
from app.models.lifecycle import PublicationStatus
from app.models.organisation import Organisation
from app.modules.bw.bw_activation.models import (
    BusinessWall,
    BWStatus,
    Partnership,
    PartnershipStatus,
)
from app.modules.wip.models.comroom.communique import Communique

if TYPE_CHECKING:
    from flask.testing import FlaskClient
    from sqlalchemy.orm import scoped_session


def _attach_bw(
    session: scoped_session, org: Organisation, owner: User, bw_type: str
) -> BusinessWall:
    bw = BusinessWall(
        bw_type=bw_type,
        status=BWStatus.ACTIVE.value,
        is_free=True,
        owner_id=owner.id,
        payer_id=owner.id,
        organisation_id=org.id,
    )
    session.add(bw)
    session.flush()
    org.bw_id = bw.id
    org.bw_active = bw_type
    session.flush()
    return bw


@pytest.fixture
def agency_setup(fresh_db, test_user: User, test_org: Organisation):
    """Turn `test_org` into a PR agency with one validated client."""
    session = fresh_db.session

    agency_bw = _attach_bw(session, test_org, test_user, "pr")
    test_org.bw_name = test_org.name

    client_org = Organisation(name=f"Client-{uuid.uuid4().hex[:6]}")
    session.add(client_org)
    session.flush()

    client_owner = User(
        email=f"client-{uuid.uuid4().hex[:6]}@example.com",
        first_name="Client",
        last_name="Owner",
        active=True,
    )
    session.add(client_owner)
    session.flush()
    client_owner.organisation_id = client_org.id
    client_bw = _attach_bw(session, client_org, client_owner, "media")
    client_org.bw_name = client_org.name

    session.add(
        Partnership(
            business_wall_id=client_bw.id,
            partner_bw_id=str(agency_bw.id),
            status=PartnershipStatus.ACTIVE.value,
            invited_by_user_id=client_owner.id,
            invited_at=datetime.now(UTC),
        )
    )
    session.commit()
    return client_org, client_owner


class TestPublisherSelectorRendering:
    def test_selector_lists_own_org_and_clients(
        self,
        fresh_db,
        logged_in_client: FlaskClient,
        test_org: Organisation,
        agency_setup,
    ):
        client_org, _ = agency_setup
        url = url_for("CommuniquesWipView:new")

        response = logged_in_client.get(url)

        assert response.status_code == 200
        body = response.data.decode()
        assert "Publier pour" in body
        assert test_org.bw_name in body
        assert client_org.bw_name in body


class TestPublishTriggersNotification:
    def test_notification_sent_when_publishing_for_validated_client(
        self,
        fresh_db,
        logged_in_client: FlaskClient,
        test_user: User,
        agency_setup,
    ):
        client_org, _ = agency_setup

        communique = Communique(owner=test_user, publisher=client_org)
        communique.titre = "Communiqué pour client"
        communique.contenu = "Contenu minimal pour publier."
        communique.status = PublicationStatus.DRAFT
        communique.publisher_id = client_org.id
        fresh_db.session.add(communique)
        fresh_db.session.commit()

        url = url_for("CommuniquesWipView:publish", id=communique.id)
        with patch(
            "app.modules.wip.crud.cbvs.communiques.notify_client_of_pr_publication"
        ) as mock_notif:
            response = logged_in_client.get(url, follow_redirects=False)

        assert response.status_code == 302
        fresh_db.session.refresh(communique)
        assert communique.status == PublicationStatus.PUBLIC
        mock_notif.assert_called_once()
        kwargs = mock_notif.call_args.kwargs
        assert kwargs["client_org"].id == client_org.id
        assert kwargs["content_type"] == "communiqué"
        assert kwargs["content_title"] == "Communiqué pour client"

    def test_no_notification_when_publishing_for_own_org(
        self,
        fresh_db,
        logged_in_client: FlaskClient,
        test_user: User,
        test_org: Organisation,
        agency_setup,
    ):
        communique = Communique(owner=test_user, publisher=test_org)
        communique.titre = "Auto publication"
        communique.contenu = "Contenu."
        communique.status = PublicationStatus.DRAFT
        communique.publisher_id = test_org.id
        fresh_db.session.add(communique)
        fresh_db.session.commit()

        url = url_for("CommuniquesWipView:publish", id=communique.id)
        with patch(
            "app.modules.wip.crud.cbvs.communiques.notify_client_of_pr_publication"
        ) as mock_notif:
            response = logged_in_client.get(url, follow_redirects=False)

        assert response.status_code == 302
        mock_notif.assert_not_called()
