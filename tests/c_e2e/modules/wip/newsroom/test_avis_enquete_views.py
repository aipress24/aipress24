# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""E2E tests for Avis d'Enquête views.

These tests verify the journalist and expert views for avis d'enquête management.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

import arrow
import pytest
from app.enums import RoleEnum
from app.flask.routing import url_for
from app.models.auth import Role, User
from app.models.organisation import Organisation
from app.modules.wip.models.newsroom.avis_enquete import (
    AvisEnquete,
    ContactAvisEnquete,
    RDVStatus,
    RDVType,
    StatutAvis,
)

from tests.c_e2e.conftest import make_authenticated_client

if TYPE_CHECKING:
    from flask import Flask
    from flask.testing import FlaskClient


# ----------------------------------------------------------------
# Fixtures
# ----------------------------------------------------------------


@pytest.fixture
def expert_role(fresh_db) -> Role:
    """Create the EXPERT role."""
    db_session = fresh_db.session
    role = Role(name=RoleEnum.EXPERT.name, description=RoleEnum.EXPERT.value)
    db_session.add(role)
    db_session.commit()
    return role


@pytest.fixture
def expert_user(fresh_db, test_org: Organisation, expert_role: Role) -> User:
    """Create an expert user."""
    db_session = fresh_db.session
    expert = User(email="expert@example.com")
    expert.photo = b""
    expert.active = True
    expert.organisation = test_org
    expert.organisation_id = test_org.id
    expert.roles.append(expert_role)
    db_session.add(expert)
    db_session.commit()
    return expert


@pytest.fixture
def test_avis_enquete(fresh_db, test_org: Organisation, test_user: User) -> AvisEnquete:
    """Create a test avis d'enquête."""
    db_session = fresh_db.session
    avis = AvisEnquete(
        owner=test_user,
        media=test_org,
        commanditaire_id=test_user.id,
        date_debut_enquete=arrow.get("2025-01-01").datetime,
        date_fin_enquete=arrow.get("2025-02-01").datetime,
        date_bouclage=arrow.get("2025-02-15").datetime,
        date_parution_prevue=arrow.get("2025-03-01").datetime,
    )
    db_session.add(avis)
    db_session.commit()
    return avis


@pytest.fixture
def contact_with_avis(
    fresh_db,
    test_avis_enquete: AvisEnquete,
    test_user: User,
    expert_user: User,
) -> ContactAvisEnquete:
    """Create a contact linked to the avis d'enquête."""
    db_session = fresh_db.session
    contact = ContactAvisEnquete(
        avis_enquete_id=test_avis_enquete.id,
        journaliste_id=test_user.id,
        expert_id=expert_user.id,
        status=StatutAvis.EN_ATTENTE,
    )
    db_session.add(contact)
    db_session.commit()
    return contact


@pytest.fixture
def accepted_contact(
    fresh_db,
    test_avis_enquete: AvisEnquete,
    test_user: User,
    expert_user: User,
) -> ContactAvisEnquete:
    """Create an accepted contact for RDV proposal tests."""
    db_session = fresh_db.session
    contact = ContactAvisEnquete(
        avis_enquete_id=test_avis_enquete.id,
        journaliste_id=test_user.id,
        expert_id=expert_user.id,
        status=StatutAvis.ACCEPTE,
        date_reponse=datetime.now(timezone.utc),
    )
    db_session.add(contact)
    db_session.commit()
    return contact


@pytest.fixture
def contact_with_rdv_proposed(
    fresh_db,
    test_avis_enquete: AvisEnquete,
    test_user: User,
    expert_user: User,
) -> ContactAvisEnquete:
    """Create a contact with RDV proposed (waiting for expert to accept)."""
    db_session = fresh_db.session
    contact = ContactAvisEnquete(
        avis_enquete_id=test_avis_enquete.id,
        journaliste_id=test_user.id,
        expert_id=expert_user.id,
        status=StatutAvis.ACCEPTE,
        date_reponse=datetime.now(timezone.utc),
        rdv_status=RDVStatus.PROPOSED,
        rdv_type=RDVType.PHONE,
        proposed_slots=[
            "2025-04-01T10:00:00+00:00",
            "2025-04-02T14:00:00+00:00",
        ],
        rdv_phone="0123456789",
    )
    db_session.add(contact)
    db_session.commit()
    return contact


@pytest.fixture
def expert_logged_in_client(app: Flask, expert_user: User) -> FlaskClient:
    """Provide a logged-in Flask test client for expert."""
    return make_authenticated_client(app, expert_user)


# ----------------------------------------------------------------
# Journalist Views Tests
# ----------------------------------------------------------------


class TestJournalistAvisEnqueteViews:
    """Tests E2E for journalist views."""

    def test_index_loads_successfully(
        self, logged_in_client: FlaskClient, test_avis_enquete: AvisEnquete
    ):
        """Index page loads successfully for authenticated journalist."""
        url = url_for("AvisEnqueteWipView:index")
        response = logged_in_client.get(url)
        assert response.status_code == 200

    def test_create_avis_enquete_form(self, logged_in_client: FlaskClient):
        """Avis d'enquête creation form loads successfully."""
        url = url_for("AvisEnqueteWipView:new")
        response = logged_in_client.get(url)
        assert response.status_code == 200

    @pytest.mark.skip(
        reason="Requires reference data (Secteur, Metier, etc.) initialization"
    )
    def test_ciblage_experts_loads(
        self, logged_in_client: FlaskClient, test_avis_enquete: AvisEnquete
    ):
        """Expert targeting (ciblage) page loads successfully.

        Note: This test requires reference data to be populated (Secteur, Metier,
        Fonction, etc.) for the ExpertFilterService selectors to work.
        """
        url = url_for("AvisEnqueteWipView:ciblage", id=test_avis_enquete.id)
        response = logged_in_client.get(url)
        assert response.status_code == 200

    def test_view_responses(
        self,
        logged_in_client: FlaskClient,
        test_avis_enquete: AvisEnquete,
        contact_with_avis: ContactAvisEnquete,
    ):
        """Responses page displays contacts."""
        url = url_for("AvisEnqueteWipView:reponses", id=test_avis_enquete.id)
        response = logged_in_client.get(url)
        assert response.status_code == 200
        # Check response contains expert email
        assert b"expert@example.com" in response.data or b"expert" in response.data

    def test_propose_rdv_form_loads(
        self,
        logged_in_client: FlaskClient,
        test_avis_enquete: AvisEnquete,
        accepted_contact: ContactAvisEnquete,
    ):
        """RDV proposal form loads for accepted contact."""
        url = url_for(
            "AvisEnqueteWipView:rdv_propose",
            id=test_avis_enquete.id,
            contact_id=accepted_contact.id,
        )
        response = logged_in_client.get(url)
        assert response.status_code == 200

    def test_rdv_management_page(
        self,
        logged_in_client: FlaskClient,
        test_avis_enquete: AvisEnquete,
        contact_with_rdv_proposed: ContactAvisEnquete,
    ):
        """RDV management page loads and shows proposed RDV."""
        url = url_for("AvisEnqueteWipView:rdv", id=test_avis_enquete.id)
        response = logged_in_client.get(url)
        assert response.status_code == 200

    def test_rdv_details_page(
        self,
        logged_in_client: FlaskClient,
        test_avis_enquete: AvisEnquete,
        contact_with_rdv_proposed: ContactAvisEnquete,
    ):
        """RDV details page loads for contact with proposed RDV."""
        url = url_for(
            "AvisEnqueteWipView:rdv_details",
            id=test_avis_enquete.id,
            contact_id=contact_with_rdv_proposed.id,
        )
        response = logged_in_client.get(url)
        assert response.status_code == 200


# ----------------------------------------------------------------
# Expert Views Tests
# ----------------------------------------------------------------


class TestExpertAvisEnqueteViews:
    """Tests E2E for expert views."""

    def test_expert_can_access_rdv_accept_page(
        self,
        expert_logged_in_client: FlaskClient,
        test_avis_enquete: AvisEnquete,
        contact_with_rdv_proposed: ContactAvisEnquete,
    ):
        """Expert can access the RDV acceptance page."""
        url = url_for(
            "AvisEnqueteWipView:rdv_accept",
            id=test_avis_enquete.id,
            contact_id=contact_with_rdv_proposed.id,
        )
        response = expert_logged_in_client.get(url)
        assert response.status_code == 200

    def test_expert_sees_proposed_slots(
        self,
        expert_logged_in_client: FlaskClient,
        test_avis_enquete: AvisEnquete,
        contact_with_rdv_proposed: ContactAvisEnquete,
    ):
        """Expert sees the proposed time slots on accept page."""
        url = url_for(
            "AvisEnqueteWipView:rdv_accept",
            id=test_avis_enquete.id,
            contact_id=contact_with_rdv_proposed.id,
        )
        response = expert_logged_in_client.get(url)
        assert response.status_code == 200
        # Page should contain slot selection elements
        assert b"selected_slot" in response.data or b"slot" in response.data.lower()

    def test_expert_cannot_access_other_expert_rdv(
        self,
        fresh_db,
        app: Flask,
        test_avis_enquete: AvisEnquete,
        contact_with_rdv_proposed: ContactAvisEnquete,
        expert_role: Role,
        test_org: Organisation,
    ):
        """Expert cannot access another expert's RDV accept page."""
        db_session = fresh_db.session

        # Create a different expert
        other_expert = User(email="other-expert@example.com")
        other_expert.photo = b""
        other_expert.active = True
        other_expert.organisation = test_org
        other_expert.organisation_id = test_org.id
        other_expert.roles.append(expert_role)
        db_session.add(other_expert)
        db_session.commit()

        # Login as the other expert
        other_expert_client = make_authenticated_client(app, other_expert)

        url = url_for(
            "AvisEnqueteWipView:rdv_accept",
            id=test_avis_enquete.id,
            contact_id=contact_with_rdv_proposed.id,
        )
        response = other_expert_client.get(url, follow_redirects=True)

        # Should be redirected with error
        assert response.status_code == 200
        # Should contain error message or be redirected to home
        assert (
            b"autoris" in response.data.lower()
            or b"home" in response.request.path.lower()
            or response.request.path == "/"
        )


# ----------------------------------------------------------------
# Access Control Tests
# ----------------------------------------------------------------


class TestAvisEnqueteAccessControl:
    """Tests for access control on avis d'enquête views."""

    def test_unauthenticated_user_redirected(self, app: Flask):
        """Unauthenticated user is redirected to login."""
        client = app.test_client()
        url = url_for("AvisEnqueteWipView:index")
        response = client.get(url, follow_redirects=False)
        # Should redirect to login
        assert response.status_code in [302, 401]

    def test_journalist_can_edit_own_avis(
        self, logged_in_client: FlaskClient, test_avis_enquete: AvisEnquete
    ):
        """Journalist can access edit form for their own avis."""
        url = url_for("AvisEnqueteWipView:edit", id=test_avis_enquete.id)
        response = logged_in_client.get(url)
        assert response.status_code == 200

    def test_view_avis_enquete_detail(
        self, logged_in_client: FlaskClient, test_avis_enquete: AvisEnquete
    ):
        """Journalist can view avis detail."""
        url = url_for("AvisEnqueteWipView:get", id=test_avis_enquete.id)
        response = logged_in_client.get(url)
        assert response.status_code == 200


# ----------------------------------------------------------------
# Form Submission Tests
# ----------------------------------------------------------------


class TestAvisEnqueteFormSubmission:
    """Tests for form submissions."""

    def test_propose_rdv_submission(
        self,
        logged_in_client: FlaskClient,
        test_avis_enquete: AvisEnquete,
        accepted_contact: ContactAvisEnquete,
    ):
        """Journalist can submit RDV proposal form."""
        url = url_for(
            "AvisEnqueteWipView:rdv_propose",
            id=test_avis_enquete.id,
            contact_id=accepted_contact.id,
        )

        form_data = {
            "rdv_type": "PHONE",
            "slot_datetime_1": "2025-04-01T10:00:00",
            "slot_datetime_2": "2025-04-02T14:00:00",
            "rdv_phone": "0123456789",
            "rdv_notes": "Test notes",
        }

        response = logged_in_client.post(url, data=form_data, follow_redirects=False)

        # Should redirect after successful submission
        assert response.status_code == 302

    def test_expert_accept_rdv_submission(
        self,
        fresh_db,
        expert_logged_in_client: FlaskClient,
        test_avis_enquete: AvisEnquete,
        contact_with_rdv_proposed: ContactAvisEnquete,
    ):
        """Expert can submit RDV acceptance form."""
        url = url_for(
            "AvisEnqueteWipView:rdv_accept",
            id=test_avis_enquete.id,
            contact_id=contact_with_rdv_proposed.id,
        )

        # Get the first proposed slot (stored as ISO string)
        first_slot = contact_with_rdv_proposed.proposed_slots[0]

        form_data = {
            "selected_slot": first_slot,  # Already ISO format
            "expert_notes": "Looking forward to our meeting",
            "action": "accept",  # to pass through the popup validation step
        }

        response = expert_logged_in_client.post(
            url,
            data=form_data,
            follow_redirects=True,  # check the rediction page content
        )

        # After submission, redirected to the opportunities list table page
        assert response.status_code == 200
        assert b"Opportunit" in response.data

        # Verify RDV status was updated
        fresh_db.session.refresh(contact_with_rdv_proposed)
        assert contact_with_rdv_proposed.rdv_status == RDVStatus.ACCEPTED

    def test_expert_refuse_rdv_submission_using_decline_slot(
        self,
        fresh_db,
        expert_logged_in_client: FlaskClient,
        test_avis_enquete: AvisEnquete,
        contact_with_rdv_proposed: ContactAvisEnquete,
    ):
        """Expert can submit RDV acceptance form but refusing all dates."""
        url = url_for(
            "AvisEnqueteWipView:rdv_accept",
            id=test_avis_enquete.id,
            contact_id=contact_with_rdv_proposed.id,
        )

        form_data = {
            "selected_slot": "decline",
            "expert_notes": "no meeting",
            "action": "accept",  # to pass through the popup validation step
        }

        response = expert_logged_in_client.post(
            url,
            data=form_data,
            follow_redirects=True,  # check the rediction page content
        )

        # After submission, redirected to the opportunities list table page
        assert response.status_code == 200
        assert b"Opportunit" in response.data

        # Verify RDV status was updated
        fresh_db.session.refresh(contact_with_rdv_proposed)
        assert contact_with_rdv_proposed.rdv_status == RDVStatus.NO_RDV

    def test_expert_refuse_rdv_submission_using_refuse_button(
        self,
        fresh_db,
        expert_logged_in_client: FlaskClient,
        test_avis_enquete: AvisEnquete,
        contact_with_rdv_proposed: ContactAvisEnquete,
    ):
        """Expert can submit RDV acceptance form but refusing all dates."""
        url = url_for(
            "AvisEnqueteWipView:rdv_accept",
            id=test_avis_enquete.id,
            contact_id=contact_with_rdv_proposed.id,
        )

        # Get the first proposed slot (stored as ISO string)
        slot = contact_with_rdv_proposed.proposed_slots[0]

        form_data = {
            "selected_slot": slot,  # can use any slot when declining
            "expert_notes": "no meeting",
            "action": "refuse",  # to pass through the popup validation step
        }

        response = expert_logged_in_client.post(
            url,
            data=form_data,
            follow_redirects=True,  # check the rediction page content
        )

        # After submission, redirected to the opportunities list table page
        assert response.status_code == 200
        assert b"Opportunit" in response.data

        # Verify RDV status was updated
        fresh_db.session.refresh(contact_with_rdv_proposed)
        assert contact_with_rdv_proposed.rdv_status == RDVStatus.NO_RDV
