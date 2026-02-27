# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""E2E tests for WIP opportunities views."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest

from app.enums import RoleEnum
from app.models.auth import KYCProfile, Role, User
from app.modules.wip.models.newsroom.avis_enquete import (
    AvisEnquete,
    ContactAvisEnquete,
    StatutAvis,
)

if TYPE_CHECKING:
    from flask.testing import FlaskClient
    from sqlalchemy.orm import Session

    from app.models.organisation import Organisation


@pytest.fixture
def journalist_user(db_session: Session, test_org: Organisation) -> User:
    """Create a journalist user who creates avis d'enquete."""
    # Check if role exists
    role = db_session.query(Role).filter_by(name=RoleEnum.PRESS_MEDIA.name).first()
    if not role:
        role = Role(
            name=RoleEnum.PRESS_MEDIA.name, description=RoleEnum.PRESS_MEDIA.value
        )
        db_session.add(role)
        db_session.flush()

    match_making = {"fonctions_journalisme": ["Journaliste"]}
    profile = KYCProfile(match_making=match_making)
    user = User(
        email="journalist@example.com",
        first_name="Jane",
        last_name="Journalist",
        active=True,
    )
    user.profile = profile
    user.organisation = test_org
    user.organisation_id = test_org.id
    user.roles.append(role)
    db_session.add(user)
    db_session.commit()
    return user


@pytest.fixture
def test_avis_enquete(
    db_session: Session,
    journalist_user: User,
    test_org: Organisation,
) -> AvisEnquete:
    """Create a test AvisEnquete."""
    now = datetime.now(UTC)
    avis = AvisEnquete(
        titre="Test Enquête",
        contenu="Looking for experts on AI",
        owner_id=journalist_user.id,
        media_id=test_org.id,
        commanditaire_id=journalist_user.id,
        date_debut_enquete=now - timedelta(days=1),
        date_fin_enquete=now + timedelta(days=7),
        date_bouclage=now + timedelta(days=10),
        date_parution_prevue=now + timedelta(days=14),
    )
    db_session.add(avis)
    db_session.commit()
    return avis


@pytest.fixture
def test_contact(
    db_session: Session,
    test_avis_enquete: AvisEnquete,
    journalist_user: User,
    test_user: User,
) -> ContactAvisEnquete:
    """Create a ContactAvisEnquete linking journalist to expert (test_user)."""
    contact = ContactAvisEnquete(
        avis_enquete_id=test_avis_enquete.id,
        journaliste_id=journalist_user.id,
        expert_id=test_user.id,
        status=StatutAvis.EN_ATTENTE,
    )
    db_session.add(contact)
    db_session.commit()
    return contact


class TestOpportunitiesListPage:
    """Tests for the opportunities list page."""

    def test_opportunities_page_loads(
        self, logged_in_client: FlaskClient, test_user: User
    ):
        """Test that opportunities page loads successfully."""
        response = logged_in_client.get("/wip/opportunities")
        assert response.status_code == 200

    def test_opportunities_page_shows_contacts(
        self,
        logged_in_client: FlaskClient,
        test_user: User,
        test_contact: ContactAvisEnquete,
    ):
        """Test that opportunities page shows user's contacts."""
        response = logged_in_client.get("/wip/opportunities")
        assert response.status_code == 200
        html = response.data.decode()
        # Should show the enquete title
        assert "Test Enquête" in html

    def test_opportunities_page_empty_when_no_contacts(
        self, logged_in_client: FlaskClient, test_user: User
    ):
        """Test opportunities page renders with no contacts."""
        response = logged_in_client.get("/wip/opportunities")
        assert response.status_code == 200


class TestOpportunityDetail:
    """Tests for viewing a single opportunity."""

    def test_view_opportunity_success(
        self,
        logged_in_client: FlaskClient,
        test_user: User,
        test_contact: ContactAvisEnquete,
    ):
        """Test viewing own opportunity."""
        response = logged_in_client.get(f"/wip/opportunities/{test_contact.id}")
        assert response.status_code == 200

    def test_view_opportunity_other_user_returns_empty(
        self,
        logged_in_client: FlaskClient,
        test_user: User,
        test_avis_enquete: AvisEnquete,
        journalist_user: User,
        db_session: Session,
    ):
        """Test viewing another user's opportunity returns empty."""
        # Create contact for another expert
        other_expert = User(
            email="other-expert@example.com",
            first_name="Other",
            last_name="Expert",
            active=True,
        )
        db_session.add(other_expert)
        db_session.flush()

        other_contact = ContactAvisEnquete(
            avis_enquete_id=test_avis_enquete.id,
            journaliste_id=journalist_user.id,
            expert_id=other_expert.id,
            status=StatutAvis.EN_ATTENTE,
        )
        db_session.add(other_contact)
        db_session.commit()

        # Try to view other expert's contact
        response = logged_in_client.get(f"/wip/opportunities/{other_contact.id}")
        # Should return empty (authorization check)
        assert response.data == b""


class TestOpportunityResponse:
    """Tests for submitting opportunity responses."""

    def test_accept_opportunity(
        self,
        logged_in_client: FlaskClient,
        test_user: User,
        test_contact: ContactAvisEnquete,
        db_session: Session,
    ):
        """Test accepting an opportunity."""
        with patch(
            "app.modules.wip.views.opportunities.send_avis_enquete_acceptance_email"
        ):
            response = logged_in_client.post(
                f"/wip/opportunities/{test_contact.id}",
                data={
                    "reponse1": "oui",
                    "contribution": "I can help with AI topics",
                },
            )

        assert response.status_code == 302  # Redirect
        assert "/wip/opportunities" in response.location

        # Check status was updated
        db_session.refresh(test_contact)
        assert test_contact.status == StatutAvis.ACCEPTE
        assert test_contact.rdv_notes_expert == "I can help with AI topics"
        assert test_contact.date_reponse is not None

    def test_accept_with_press_relation(
        self,
        logged_in_client: FlaskClient,
        test_user: User,
        test_contact: ContactAvisEnquete,
        db_session: Session,
    ):
        """Test accepting with press relation option."""
        with patch(
            "app.modules.wip.views.opportunities.send_avis_enquete_acceptance_email"
        ):
            response = logged_in_client.post(
                f"/wip/opportunities/{test_contact.id}",
                data={
                    "reponse1": "oui_relation_presse",
                    "contribution": "Contact my PR team",
                },
            )

        assert response.status_code == 302

        db_session.refresh(test_contact)
        assert test_contact.status == StatutAvis.ACCEPTE_RELATION_PRESSE

    def test_refuse_opportunity(
        self,
        logged_in_client: FlaskClient,
        test_user: User,
        test_contact: ContactAvisEnquete,
        db_session: Session,
    ):
        """Test refusing an opportunity."""
        with patch(
            "app.modules.wip.views.opportunities.send_avis_enquete_acceptance_email"
        ):
            response = logged_in_client.post(
                f"/wip/opportunities/{test_contact.id}",
                data={"reponse1": "non"},
            )

        assert response.status_code == 302

        db_session.refresh(test_contact)
        assert test_contact.status == StatutAvis.REFUSE

    def test_refuse_with_suggestion(
        self,
        logged_in_client: FlaskClient,
        test_user: User,
        test_contact: ContactAvisEnquete,
        db_session: Session,
    ):
        """Test refusing with a suggestion."""
        with patch(
            "app.modules.wip.views.opportunities.send_avis_enquete_acceptance_email"
        ):
            response = logged_in_client.post(
                f"/wip/opportunities/{test_contact.id}",
                data={
                    "reponse1": "non-mais",
                    "suggestion": "Try contacting Dr. Smith instead",
                },
            )

        assert response.status_code == 302

        db_session.refresh(test_contact)
        assert test_contact.status == StatutAvis.REFUSE_SUGGESTION
        assert test_contact.rdv_notes_expert == "Try contacting Dr. Smith instead"


class TestOpportunityFormUpdate:
    """Tests for HTMX form partial updates."""

    def test_form_update_renders_without_saving(
        self,
        logged_in_client: FlaskClient,
        test_user: User,
        test_contact: ContactAvisEnquete,
        db_session: Session,
    ):
        """Test that form update renders without saving data."""
        original_status = test_contact.status

        response = logged_in_client.post(
            f"/wip/opportunities/{test_contact.id}/form",
            data={"reponse1": "oui"},
        )

        assert response.status_code == 200

        # Status should NOT have changed
        db_session.refresh(test_contact)
        assert test_contact.status == original_status


class TestMediaOpportunityClass:
    """Tests for the MediaOpportunity data class."""

    def test_media_opportunity_properties(
        self,
        db_session: Session,
        test_org: Organisation,
    ):
        """Test MediaOpportunity exposes correct properties."""
        from datetime import UTC, datetime, timedelta

        from app.modules.wip.views.opportunities import MediaOpportunity

        # Create journalist inline to avoid fixture ordering issues
        journalist = User(
            email="journalist-for-class-test@example.com",
            first_name="Test",
            last_name="Journalist",
            active=True,
        )
        journalist.organisation = test_org
        db_session.add(journalist)
        db_session.flush()

        now = datetime.now(UTC)
        avis = AvisEnquete(
            titre="Test Enquête",
            contenu="Looking for experts on AI",
            owner_id=journalist.id,
            media_id=test_org.id,
            commanditaire_id=journalist.id,
            date_debut_enquete=now - timedelta(days=1),
            date_fin_enquete=now + timedelta(days=7),
            date_bouclage=now + timedelta(days=10),
            date_parution_prevue=now + timedelta(days=14),
        )
        db_session.add(avis)
        db_session.commit()

        media_opp = MediaOpportunity(
            id=1,
            journaliste=journalist,
            avis_enquete=avis,
        )

        assert media_opp.titre == "Test Enquête"
        assert media_opp.brief == "Looking for experts on AI"
        assert media_opp.journaliste == journalist
