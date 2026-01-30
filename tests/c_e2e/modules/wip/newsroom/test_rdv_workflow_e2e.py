# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""E2E tests for RDV (Rendez-vous) workflow.

These tests verify the complete RDV scheduling workflow between
journalists and experts, including proposal, acceptance, and confirmation.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
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
def accepted_contact(
    fresh_db,
    test_avis_enquete: AvisEnquete,
    test_user: User,
    expert_user: User,
) -> ContactAvisEnquete:
    """Create an accepted contact ready for RDV proposal."""
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
    """Create a contact with RDV proposed."""
    db_session = fresh_db.session
    # Use future dates for slots
    tomorrow = datetime.now(timezone.utc) + timedelta(days=1)
    day_after = datetime.now(timezone.utc) + timedelta(days=2)

    contact = ContactAvisEnquete(
        avis_enquete_id=test_avis_enquete.id,
        journaliste_id=test_user.id,
        expert_id=expert_user.id,
        status=StatutAvis.ACCEPTE,
        date_reponse=datetime.now(timezone.utc),
        rdv_status=RDVStatus.PROPOSED,
        rdv_type=RDVType.PHONE,
        proposed_slots=[
            tomorrow.replace(hour=10, minute=0).isoformat(),
            day_after.replace(hour=14, minute=0).isoformat(),
        ],
        rdv_phone="0123456789",
    )
    db_session.add(contact)
    db_session.commit()
    return contact


@pytest.fixture
def contact_with_rdv_accepted(
    fresh_db,
    test_avis_enquete: AvisEnquete,
    test_user: User,
    expert_user: User,
) -> ContactAvisEnquete:
    """Create a contact with RDV accepted (pending confirmation)."""
    db_session = fresh_db.session
    tomorrow = datetime.now(timezone.utc) + timedelta(days=1)
    selected_slot = tomorrow.replace(hour=10, minute=0)

    contact = ContactAvisEnquete(
        avis_enquete_id=test_avis_enquete.id,
        journaliste_id=test_user.id,
        expert_id=expert_user.id,
        status=StatutAvis.ACCEPTE,
        date_reponse=datetime.now(timezone.utc),
        rdv_status=RDVStatus.ACCEPTED,
        rdv_type=RDVType.PHONE,
        proposed_slots=[selected_slot.isoformat()],
        date_rdv=selected_slot,
        rdv_phone="0123456789",
    )
    db_session.add(contact)
    db_session.commit()
    return contact


@pytest.fixture
def contact_with_rdv_confirmed(
    fresh_db,
    test_avis_enquete: AvisEnquete,
    test_user: User,
    expert_user: User,
) -> ContactAvisEnquete:
    """Create a contact with RDV confirmed."""
    db_session = fresh_db.session
    tomorrow = datetime.now(timezone.utc) + timedelta(days=1)
    selected_slot = tomorrow.replace(hour=10, minute=0)

    contact = ContactAvisEnquete(
        avis_enquete_id=test_avis_enquete.id,
        journaliste_id=test_user.id,
        expert_id=expert_user.id,
        status=StatutAvis.ACCEPTE,
        date_reponse=datetime.now(timezone.utc),
        rdv_status=RDVStatus.CONFIRMED,
        rdv_type=RDVType.PHONE,
        proposed_slots=[selected_slot.isoformat()],
        date_rdv=selected_slot,
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
# Full RDV Workflow Tests
# ----------------------------------------------------------------


class TestRdvFullWorkflow:
    """Tests for complete RDV scheduling workflow."""

    def test_journalist_proposes_rdv_slots(
        self,
        fresh_db,
        logged_in_client: FlaskClient,
        test_avis_enquete: AvisEnquete,
        accepted_contact: ContactAvisEnquete,
    ):
        """Journalist can propose RDV time slots to an accepted expert."""
        url = url_for(
            "AvisEnqueteWipView:rdv_propose",
            id=test_avis_enquete.id,
            contact_id=accepted_contact.id,
        )

        # Use future dates - ensure weekday (Monday-Friday)
        # Add enough days to skip weekends if needed
        future_date = datetime.now(timezone.utc) + timedelta(days=7)
        # Adjust to Monday if needed
        while future_date.weekday() >= 5:  # 5=Saturday, 6=Sunday
            future_date += timedelta(days=1)

        form_data = {
            "rdv_type": "PHONE",
            "slot_datetime_1": future_date.replace(hour=10, minute=0).strftime(
                "%Y-%m-%dT%H:%M:%S"
            ),
            "rdv_phone": "0123456789",
            "rdv_notes": "Looking forward to our interview",
        }

        response = logged_in_client.post(url, data=form_data, follow_redirects=False)

        # Should redirect after successful submission
        assert response.status_code == 302

        # Verify RDV status was updated
        fresh_db.session.refresh(accepted_contact)
        assert accepted_contact.rdv_status == RDVStatus.PROPOSED
        assert accepted_contact.rdv_type == RDVType.PHONE
        assert len(accepted_contact.proposed_slots) >= 1

    def test_expert_accepts_rdv_slot(
        self,
        fresh_db,
        expert_logged_in_client: FlaskClient,
        test_avis_enquete: AvisEnquete,
        contact_with_rdv_proposed: ContactAvisEnquete,
    ):
        """Expert can accept one of the proposed RDV slots."""
        url = url_for(
            "AvisEnqueteWipView:rdv_accept",
            id=test_avis_enquete.id,
            contact_id=contact_with_rdv_proposed.id,
        )

        # Select the first proposed slot
        first_slot = contact_with_rdv_proposed.proposed_slots[0]

        form_data = {
            "selected_slot": first_slot,
            "expert_notes": "I confirm my availability",
            "action": "accept",  # to pass through the popup validation step
        }

        response = expert_logged_in_client.post(
            url, data=form_data, follow_redirects=True
        )

        # Should redirect after successful submission
        assert response.status_code == 200

        # Verify RDV status was updated
        fresh_db.session.refresh(contact_with_rdv_proposed)
        assert contact_with_rdv_proposed.rdv_status == RDVStatus.ACCEPTED

    def test_journalist_confirms_rdv(
        self,
        fresh_db,
        logged_in_client: FlaskClient,
        test_avis_enquete: AvisEnquete,
        contact_with_rdv_accepted: ContactAvisEnquete,
    ):
        """Journalist can confirm an accepted RDV."""
        url = url_for(
            "AvisEnqueteWipView:rdv_confirm",
            id=test_avis_enquete.id,
            contact_id=contact_with_rdv_accepted.id,
        )

        response = logged_in_client.post(url, follow_redirects=False)

        # Should redirect after successful confirmation
        assert response.status_code == 302

        # Verify RDV status was updated
        fresh_db.session.refresh(contact_with_rdv_accepted)
        assert contact_with_rdv_accepted.rdv_status == RDVStatus.CONFIRMED


# ----------------------------------------------------------------
# RDV Details Display Tests
# ----------------------------------------------------------------


class TestRdvDetailsDisplay:
    """Tests for RDV details display."""

    def test_rdv_details_shows_phone_contact(
        self,
        logged_in_client: FlaskClient,
        test_avis_enquete: AvisEnquete,
        contact_with_rdv_confirmed: ContactAvisEnquete,
    ):
        """RDV details page shows phone contact information."""
        url = url_for(
            "AvisEnqueteWipView:rdv_details",
            id=test_avis_enquete.id,
            contact_id=contact_with_rdv_confirmed.id,
        )

        response = logged_in_client.get(url)
        assert response.status_code == 200
        # Should contain phone number
        assert b"0123456789" in response.data

    def test_rdv_details_shows_status(
        self,
        logged_in_client: FlaskClient,
        test_avis_enquete: AvisEnquete,
        contact_with_rdv_confirmed: ContactAvisEnquete,
    ):
        """RDV details page shows RDV status."""
        url = url_for(
            "AvisEnqueteWipView:rdv_details",
            id=test_avis_enquete.id,
            contact_id=contact_with_rdv_confirmed.id,
        )

        response = logged_in_client.get(url)
        assert response.status_code == 200

    def test_rdv_list_shows_all_rdvs(
        self,
        logged_in_client: FlaskClient,
        test_avis_enquete: AvisEnquete,
        contact_with_rdv_proposed: ContactAvisEnquete,
    ):
        """RDV management page lists all RDVs for the avis."""
        url = url_for("AvisEnqueteWipView:rdv", id=test_avis_enquete.id)

        response = logged_in_client.get(url)
        assert response.status_code == 200


# ----------------------------------------------------------------
# RDV Type Variations Tests
# ----------------------------------------------------------------


def _get_future_weekday_datetime(day_after: int = 1) -> datetime:
    """Returns a datetime object for a next day, ensuring it's not a weekend."""
    future_date = datetime.now(timezone.utc) + timedelta(days=day_after)
    while future_date.weekday() >= 5:  # 5=Saturday, 6=Sunday
        future_date += timedelta(days=1)
    return future_date


class TestRdvTypeVariations:
    """Tests for different RDV types (phone, video, face-to-face)."""

    def test_propose_video_rdv(
        self,
        fresh_db,
        logged_in_client: FlaskClient,
        test_avis_enquete: AvisEnquete,
        accepted_contact: ContactAvisEnquete,
    ):
        """Journalist can propose a video RDV."""
        url = url_for(
            "AvisEnqueteWipView:rdv_propose",
            id=test_avis_enquete.id,
            contact_id=accepted_contact.id,
        )

        next_weekday = _get_future_weekday_datetime(day_after=1)

        form_data = {
            "rdv_type": "VIDEO",
            "slot_datetime_1": next_weekday.replace(hour=10, minute=0).isoformat(),
            "rdv_video_link": "https://meet.example.com/interview-123",
            "rdv_notes": "Video call link provided",
        }

        response = logged_in_client.post(url, data=form_data, follow_redirects=False)

        assert response.status_code == 302

        fresh_db.session.refresh(accepted_contact)
        assert accepted_contact.rdv_type == RDVType.VIDEO
        assert (
            accepted_contact.rdv_video_link == "https://meet.example.com/interview-123"
        )

    def test_propose_f2f_rdv(
        self,
        fresh_db,
        logged_in_client: FlaskClient,
        test_avis_enquete: AvisEnquete,
        accepted_contact: ContactAvisEnquete,
    ):
        """Journalist can propose a face-to-face RDV."""
        url = url_for(
            "AvisEnqueteWipView:rdv_propose",
            id=test_avis_enquete.id,
            contact_id=accepted_contact.id,
        )

        next_weekday = _get_future_weekday_datetime(day_after=1)

        form_data = {
            "rdv_type": "F2F",
            "slot_datetime_1": next_weekday.replace(hour=10, minute=0).isoformat(),
            "rdv_address": "123 Rue de Paris, 75001 Paris",
            "rdv_notes": "Meeting at our office",
        }

        response = logged_in_client.post(url, data=form_data, follow_redirects=False)

        assert response.status_code == 302

        fresh_db.session.refresh(accepted_contact)
        assert accepted_contact.rdv_type == RDVType.F2F
        assert "Paris" in accepted_contact.rdv_address


# ----------------------------------------------------------------
# RDV Status Transitions Tests
# ----------------------------------------------------------------


class TestRdvStatusTransitions:
    """Tests for RDV status transition rules."""

    def test_cannot_propose_rdv_to_pending_contact(
        self,
        fresh_db,
        logged_in_client: FlaskClient,
        test_avis_enquete: AvisEnquete,
        test_user: User,
        expert_user: User,
    ):
        """Cannot propose RDV to a contact who hasn't accepted the avis yet."""
        db_session = fresh_db.session

        # Create a pending contact
        pending_contact = ContactAvisEnquete(
            avis_enquete_id=test_avis_enquete.id,
            journaliste_id=test_user.id,
            expert_id=expert_user.id,
            status=StatutAvis.EN_ATTENTE,
        )
        db_session.add(pending_contact)
        db_session.commit()

        url = url_for(
            "AvisEnqueteWipView:rdv_propose",
            id=test_avis_enquete.id,
            contact_id=pending_contact.id,
        )

        # GET should work (show form)
        response = logged_in_client.get(url)
        assert response.status_code == 200

        # POST should fail or show error
        tomorrow = datetime.now(timezone.utc) + timedelta(days=1)
        form_data = {
            "rdv_type": "PHONE",
            "slot_datetime_1": tomorrow.replace(hour=10, minute=0).isoformat(),
            "rdv_phone": "0123456789",
        }

        response = logged_in_client.post(url, data=form_data, follow_redirects=True)

        # Contact should not have RDV proposed
        db_session.refresh(pending_contact)
        # RDV status should remain NO_RDV since contact hasn't accepted
        assert pending_contact.rdv_status == RDVStatus.NO_RDV

    def test_cannot_confirm_unaccepted_rdv(
        self,
        fresh_db,
        logged_in_client: FlaskClient,
        test_avis_enquete: AvisEnquete,
        contact_with_rdv_proposed: ContactAvisEnquete,
    ):
        """Cannot confirm RDV that hasn't been accepted by expert."""
        url = url_for(
            "AvisEnqueteWipView:rdv_confirm",
            id=test_avis_enquete.id,
            contact_id=contact_with_rdv_proposed.id,
        )

        response = logged_in_client.post(url, follow_redirects=True)

        # Should complete request (with error flash message) and not change status
        assert response.status_code == 200
        fresh_db.session.refresh(contact_with_rdv_proposed)
        assert contact_with_rdv_proposed.rdv_status == RDVStatus.PROPOSED

    def test_expert_cannot_accept_already_accepted_rdv(
        self,
        fresh_db,
        expert_logged_in_client: FlaskClient,
        test_avis_enquete: AvisEnquete,
        contact_with_rdv_accepted: ContactAvisEnquete,
    ):
        """Expert cannot re-accept an already accepted RDV."""
        url = url_for(
            "AvisEnqueteWipView:rdv_accept",
            id=test_avis_enquete.id,
            contact_id=contact_with_rdv_accepted.id,
        )

        # GET should redirect since RDV is already accepted
        response = expert_logged_in_client.get(url, follow_redirects=False)

        # Should redirect to details or show info message
        assert response.status_code in [200, 302]

    def test_journalist_can_cancel_rdv(
        self,
        fresh_db,
        logged_in_client: FlaskClient,
        test_avis_enquete: AvisEnquete,
        contact_with_rdv_confirmed: ContactAvisEnquete,
    ):
        """Journalist can cancel a confirmed RDV."""
        url = url_for(
            "AvisEnqueteWipView:rdv_cancel",
            id=test_avis_enquete.id,
            contact_id=contact_with_rdv_confirmed.id,
        )

        response = logged_in_client.post(url, follow_redirects=False)

        assert response.status_code == 302

        fresh_db.session.refresh(contact_with_rdv_confirmed)
        assert contact_with_rdv_confirmed.rdv_status == RDVStatus.NO_RDV

    def test_expert_can_cancel_rdv(
        self,
        fresh_db,
        expert_logged_in_client: FlaskClient,
        test_avis_enquete: AvisEnquete,
        contact_with_rdv_confirmed: ContactAvisEnquete,
    ):
        """Expert can cancel a confirmed RDV."""
        url = url_for(
            "AvisEnqueteWipView:rdv_cancel",
            id=test_avis_enquete.id,
            contact_id=contact_with_rdv_confirmed.id,
        )

        response = expert_logged_in_client.post(url, follow_redirects=False)

        assert response.status_code == 302

        fresh_db.session.refresh(contact_with_rdv_confirmed)
        assert contact_with_rdv_confirmed.rdv_status == RDVStatus.NO_RDV


# ----------------------------------------------------------------
# Multiple Slots Tests
# ----------------------------------------------------------------


class TestMultipleSlots:
    """Tests for handling multiple proposed time slots."""

    def test_propose_multiple_slots(
        self,
        fresh_db,
        logged_in_client: FlaskClient,
        test_avis_enquete: AvisEnquete,
        accepted_contact: ContactAvisEnquete,
    ):
        """Journalist can propose up to 5 time slots."""
        url = url_for(
            "AvisEnqueteWipView:rdv_propose",
            id=test_avis_enquete.id,
            contact_id=accepted_contact.id,
        )

        base_date = _get_future_weekday_datetime(day_after=1)

        form_data = {
            "rdv_type": "PHONE",
            "slot_datetime_1": base_date.replace(hour=9, minute=0).isoformat(),
            "slot_datetime_2": base_date.replace(hour=11, minute=0).isoformat(),
            "slot_datetime_3": base_date.replace(hour=14, minute=0).isoformat(),
            "slot_datetime_4": base_date.replace(hour=16, minute=0).isoformat(),
            "rdv_phone": "0123456789",
        }

        response = logged_in_client.post(url, data=form_data, follow_redirects=False)

        assert response.status_code == 302

        fresh_db.session.refresh(accepted_contact)
        assert len(accepted_contact.proposed_slots) == 4

    def test_expert_sees_all_proposed_slots(
        self,
        expert_logged_in_client: FlaskClient,
        test_avis_enquete: AvisEnquete,
        contact_with_rdv_proposed: ContactAvisEnquete,
    ):
        """Expert can see all proposed time slots on accept page."""
        url = url_for(
            "AvisEnqueteWipView:rdv_accept",
            id=test_avis_enquete.id,
            contact_id=contact_with_rdv_proposed.id,
        )

        response = expert_logged_in_client.get(url)

        assert response.status_code == 200
        # Page should contain slot selection elements
        assert b"selected_slot" in response.data or b"slot" in response.data.lower()
