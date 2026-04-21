# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""End-to-end tests for Partnership-based publication authorization.

A PR agency user may only publish communiqués attributed to their own
organisation or to a client with whom an active Partnership exists.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

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


def _make_org(session: scoped_session, name: str) -> Organisation:
    org = Organisation(name=f"{name}-{uuid.uuid4().hex[:6]}")
    session.add(org)
    session.flush()
    return org


@pytest.fixture
def agency_setup(fresh_db, test_user: User, test_org: Organisation):
    """Promote `test_user`/`test_org` to a PR agency with one validated client.

    Returns (client_org, validated_partnership).
    """
    session = fresh_db.session

    agency_bw = _attach_bw(session, test_org, test_user, "pr")

    client_org = _make_org(session, "Client")
    client_owner = User(
        email=f"client-owner-{uuid.uuid4().hex[:6]}@example.com",
        first_name="Client",
        last_name="Owner",
        active=True,
    )
    session.add(client_owner)
    session.flush()
    client_owner.organisation_id = client_org.id
    client_bw = _attach_bw(session, client_org, client_owner, "media")

    partnership = Partnership(
        business_wall_id=client_bw.id,
        partner_bw_id=str(agency_bw.id),
        status=PartnershipStatus.ACTIVE.value,
        invited_by_user_id=client_owner.id,
        invited_at=datetime.now(UTC),
    )
    session.add(partnership)
    session.commit()

    return client_org, partnership


@pytest.fixture
def stranger_org(fresh_db) -> Organisation:
    """An organisation unrelated to the PR agency user."""
    session = fresh_db.session
    org = _make_org(session, "Stranger")
    session.commit()
    return org


def _draft_communique_for(
    session: scoped_session,
    owner: User,
    publisher: Organisation,
    titre: str = "Communiqué de test",
) -> Communique:
    c = Communique(owner=owner, publisher=publisher)
    c.titre = titre
    c.contenu = "Contenu minimal pour pouvoir publier."
    c.status = PublicationStatus.DRAFT
    session.add(c)
    session.commit()
    return c


class TestPublishForValidatedClient:
    def test_publish_for_own_org_is_allowed(
        self,
        fresh_db,
        logged_in_client: FlaskClient,
        test_user: User,
        test_org: Organisation,
        agency_setup,
    ):
        communique = _draft_communique_for(fresh_db.session, test_user, test_org)
        url = url_for("CommuniquesWipView:publish", id=communique.id)

        response = logged_in_client.get(url, follow_redirects=False)

        assert response.status_code == 302
        fresh_db.session.refresh(communique)
        assert communique.status == PublicationStatus.PUBLIC

    def test_publish_for_validated_client_is_allowed(
        self,
        fresh_db,
        logged_in_client: FlaskClient,
        test_user: User,
        agency_setup,
    ):
        client_org, _ = agency_setup
        communique = _draft_communique_for(fresh_db.session, test_user, client_org)
        url = url_for("CommuniquesWipView:publish", id=communique.id)

        response = logged_in_client.get(url, follow_redirects=False)

        assert response.status_code == 302
        fresh_db.session.refresh(communique)
        assert communique.status == PublicationStatus.PUBLIC
        assert communique.publisher_id == client_org.id

    def test_publish_for_stranger_org_is_rejected(
        self,
        fresh_db,
        logged_in_client: FlaskClient,
        test_user: User,
        agency_setup,
        stranger_org: Organisation,
    ):
        communique = _draft_communique_for(fresh_db.session, test_user, stranger_org)
        url = url_for("CommuniquesWipView:publish", id=communique.id)

        response = logged_in_client.get(url, follow_redirects=False)

        # Rejected -> redirect back to edit page, still DRAFT.
        assert response.status_code == 302
        assert (
            "/edit/" in response.headers.get("Location", "")
            or "/new" in (response.headers.get("Location") or "")
            or "edit" in (response.headers.get("Location") or "").lower()
        )
        fresh_db.session.refresh(communique)
        assert communique.status == PublicationStatus.DRAFT

    def test_publish_for_revoked_client_is_rejected(
        self,
        fresh_db,
        logged_in_client: FlaskClient,
        test_user: User,
        agency_setup,
    ):
        client_org, partnership = agency_setup
        partnership.status = PartnershipStatus.REVOKED.value
        fresh_db.session.commit()

        communique = _draft_communique_for(fresh_db.session, test_user, client_org)
        url = url_for("CommuniquesWipView:publish", id=communique.id)

        response = logged_in_client.get(url, follow_redirects=False)

        assert response.status_code == 302
        fresh_db.session.refresh(communique)
        assert communique.status == PublicationStatus.DRAFT
