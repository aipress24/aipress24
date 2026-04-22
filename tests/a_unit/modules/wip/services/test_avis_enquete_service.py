# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Tests for AvisEnqueteService."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING
from unittest.mock import patch

import arrow
import pytest

from app.models.auth import KYCProfile, User
from app.models.organisation import Organisation
from app.modules.wip.models import (
    AvisEnquete,
    ContactAvisEnquete,
    RDVStatus,
    RDVType,
    StatutAvis,
)
from app.modules.wip.services.newsroom import (
    AvisEnqueteService,
    RDVAcceptanceData,
    RDVProposalData,
)

if TYPE_CHECKING:
    from sqlalchemy.orm import scoped_session


def _get_next_weekday_slot(days_ahead: int = 1, hour: int = 10) -> datetime:
    """Get a valid future weekday slot at the given hour."""
    now = datetime.now(UTC)
    target = now + timedelta(days=days_ahead)
    while target.weekday() >= 5:  # Skip weekends
        target += timedelta(days=1)
    return target.replace(hour=hour, minute=0, second=0, microsecond=0)


def _create_test_enquete(
    db_session: scoped_session,
    journaliste: User,
    media: Organisation,
) -> AvisEnquete:
    """Create a test AvisEnquete."""
    enquete = AvisEnquete(
        owner=journaliste,
        media=media,
        commanditaire_id=journaliste.id,
        date_debut_enquete=arrow.get("2025-01-01").datetime,
        date_fin_enquete=arrow.get("2025-02-01").datetime,
        date_bouclage=arrow.get("2025-02-15").datetime,
        date_parution_prevue=arrow.get("2025-03-01").datetime,
    )
    db_session.add(enquete)
    db_session.flush()
    return enquete


def _create_test_contact(
    db_session: scoped_session,
    enquete: AvisEnquete,
    journaliste: User,
    expert: User,
    status: StatutAvis = StatutAvis.ACCEPTE,
) -> ContactAvisEnquete:
    """Create a test ContactAvisEnquete."""
    contact = ContactAvisEnquete(
        avis_enquete_id=enquete.id,
        journaliste_id=journaliste.id,
        expert_id=expert.id,
        status=status,
    )
    db_session.add(contact)
    db_session.flush()
    return contact


class TestAvisEnqueteServicePropose:
    """Tests for propose_rdv method."""

    def test_propose_rdv_success(self, db_session: scoped_session) -> None:
        """Service should successfully propose RDV."""
        # Setup
        journaliste = User(email="j@test.com")
        expert = User(email="e@test.com")
        media = Organisation(name="Media")
        db_session.add_all([journaliste, expert, media])
        db_session.flush()

        enquete = _create_test_enquete(db_session, journaliste, media)
        contact = _create_test_contact(
            db_session, enquete, journaliste, expert, StatutAvis.ACCEPTE
        )

        # Act - pass db_session explicitly
        service = AvisEnqueteService(db_session=db_session)
        future_slot = _get_next_weekday_slot()
        data = RDVProposalData(
            rdv_type=RDVType.PHONE,
            proposed_slots=[future_slot],
            rdv_phone="+33612345678",
        )

        result = service.propose_rdv(contact.id, data, "/notification")

        # Assert
        assert result.rdv_status == RDVStatus.PROPOSED
        assert result.rdv_type == RDVType.PHONE
        assert len(result.proposed_slots) == 1
        assert result.rdv_phone == "+33612345678"

    def test_propose_rdv_with_video(self, db_session: scoped_session) -> None:
        """Service should handle VIDEO type RDV."""
        journaliste = User(email="j@test.com")
        expert = User(email="e@test.com")
        media = Organisation(name="Media")
        db_session.add_all([journaliste, expert, media])
        db_session.flush()

        enquete = _create_test_enquete(db_session, journaliste, media)
        contact = _create_test_contact(
            db_session, enquete, journaliste, expert, StatutAvis.ACCEPTE
        )

        service = AvisEnqueteService(db_session=db_session)
        future_slot = _get_next_weekday_slot()
        data = RDVProposalData(
            rdv_type=RDVType.VIDEO,
            proposed_slots=[future_slot],
            rdv_video_link="https://meet.google.com/abc",
        )

        result = service.propose_rdv(contact.id, data, "/notification")

        assert result.rdv_status == RDVStatus.PROPOSED
        assert result.rdv_type == RDVType.VIDEO
        assert result.rdv_video_link == "https://meet.google.com/abc"

    def test_propose_rdv_contact_not_found(self, db_session: scoped_session) -> None:
        """Service should raise LookupError for missing contact."""
        service = AvisEnqueteService(db_session=db_session)
        future_slot = _get_next_weekday_slot()
        data = RDVProposalData(
            rdv_type=RDVType.PHONE,
            proposed_slots=[future_slot],
            rdv_phone="+33612345678",
        )

        with pytest.raises(LookupError, match="Contact not found"):
            service.propose_rdv(99999, data, "/notification")

    def test_propose_rdv_validation_error(self, db_session: scoped_session) -> None:
        """Service should propagate validation errors from domain."""
        journaliste = User(email="j@test.com")
        expert = User(email="e@test.com")
        media = Organisation(name="Media")
        db_session.add_all([journaliste, expert, media])
        db_session.flush()

        enquete = _create_test_enquete(db_session, journaliste, media)
        # Contact NOT accepted - cannot propose RDV
        contact = _create_test_contact(
            db_session, enquete, journaliste, expert, StatutAvis.EN_ATTENTE
        )

        service = AvisEnqueteService(db_session=db_session)
        future_slot = _get_next_weekday_slot()
        data = RDVProposalData(
            rdv_type=RDVType.PHONE,
            proposed_slots=[future_slot],
            rdv_phone="+33612345678",
        )

        with pytest.raises(ValueError, match="expert has not accepted"):
            service.propose_rdv(contact.id, data, "/notification")


class TestAvisEnqueteServiceAccept:
    """Tests for accept_rdv method."""

    def test_accept_rdv_success(self, db_session: scoped_session) -> None:
        """Service should successfully accept RDV."""
        journaliste = User(email="j@test.com")
        expert = User(email="e@test.com")
        media = Organisation(name="Media")
        db_session.add_all([journaliste, expert, media])
        db_session.flush()

        enquete = _create_test_enquete(db_session, journaliste, media)
        contact = _create_test_contact(
            db_session, enquete, journaliste, expert, StatutAvis.ACCEPTE
        )

        # First propose
        service = AvisEnqueteService(db_session=db_session)
        future_slot = _get_next_weekday_slot()
        propose_data = RDVProposalData(
            rdv_type=RDVType.PHONE,
            proposed_slots=[future_slot],
            rdv_phone="+33612345678",
        )
        service.propose_rdv(contact.id, propose_data, "/notification")

        # Then accept
        accept_data = RDVAcceptanceData(
            selected_slot=future_slot,
            expert_notes="Looking forward to it",
        )
        result = service.accept_rdv(contact.id, accept_data, "/notification")

        assert result.rdv_status == RDVStatus.ACCEPTED
        assert result.date_rdv == future_slot
        assert result.rdv_notes_expert == "Looking forward to it"

    def test_accept_rdv_contact_not_found(self, db_session: scoped_session) -> None:
        """Service should raise LookupError for missing contact."""
        service = AvisEnqueteService(db_session=db_session)
        future_slot = _get_next_weekday_slot()
        accept_data = RDVAcceptanceData(selected_slot=future_slot)

        with pytest.raises(LookupError, match="Contact not found"):
            service.accept_rdv(99999, accept_data, "/notification")

    def test_accept_rdv_no_proposal(self, db_session: scoped_session) -> None:
        """Service should propagate error if no RDV was proposed."""
        journaliste = User(email="j@test.com")
        expert = User(email="e@test.com")
        media = Organisation(name="Media")
        db_session.add_all([journaliste, expert, media])
        db_session.flush()

        enquete = _create_test_enquete(db_session, journaliste, media)
        contact = _create_test_contact(
            db_session, enquete, journaliste, expert, StatutAvis.ACCEPTE
        )

        service = AvisEnqueteService(db_session=db_session)
        future_slot = _get_next_weekday_slot()
        accept_data = RDVAcceptanceData(selected_slot=future_slot)

        with pytest.raises(ValueError, match="no RDV has been proposed"):
            service.accept_rdv(contact.id, accept_data, "/notification")


class TestAvisEnqueteServiceCancel:
    """Tests for cancel_rdv method."""

    def test_cancel_rdv_success(self, db_session: scoped_session) -> None:
        """Service should successfully cancel RDV."""
        journaliste = User(email="j@test.com")
        expert = User(email="e@test.com")
        media = Organisation(name="Media")
        db_session.add_all([journaliste, expert, media])
        db_session.flush()

        enquete = _create_test_enquete(db_session, journaliste, media)
        contact = _create_test_contact(
            db_session, enquete, journaliste, expert, StatutAvis.ACCEPTE
        )

        # Propose and accept first
        service = AvisEnqueteService(db_session=db_session)
        future_slot = _get_next_weekday_slot()
        propose_data = RDVProposalData(
            rdv_type=RDVType.PHONE,
            proposed_slots=[future_slot],
            rdv_phone="+33612345678",
        )
        service.propose_rdv(contact.id, propose_data, "/notification")

        accept_data = RDVAcceptanceData(selected_slot=future_slot)
        service.accept_rdv(contact.id, accept_data, "/notification")

        # Now cancel
        result = service.cancel_rdv(contact.id)

        assert result.rdv_status == RDVStatus.NO_RDV
        assert result.rdv_type is None
        assert result.date_rdv is None

    def test_cancel_rdv_no_rdv(self, db_session: scoped_session) -> None:
        """Service should propagate error if no RDV to cancel."""
        journaliste = User(email="j@test.com")
        expert = User(email="e@test.com")
        media = Organisation(name="Media")
        db_session.add_all([journaliste, expert, media])
        db_session.flush()

        enquete = _create_test_enquete(db_session, journaliste, media)
        contact = _create_test_contact(
            db_session, enquete, journaliste, expert, StatutAvis.ACCEPTE
        )

        service = AvisEnqueteService(db_session=db_session)

        with pytest.raises(ValueError, match="No RDV to cancel"):
            service.cancel_rdv(contact.id)


class TestAvisEnqueteServiceQueries:
    """Tests for query methods."""

    def test_get_contact(self, db_session: scoped_session) -> None:
        """Service should return contact by ID."""
        journaliste = User(email="j@test.com")
        expert = User(email="e@test.com")
        media = Organisation(name="Media")
        db_session.add_all([journaliste, expert, media])
        db_session.flush()

        enquete = _create_test_enquete(db_session, journaliste, media)
        contact = _create_test_contact(
            db_session, enquete, journaliste, expert, StatutAvis.ACCEPTE
        )

        service = AvisEnqueteService(db_session=db_session)
        result = service.get_contact(contact.id)

        assert result is not None
        assert result.id == contact.id

    def test_get_contact_not_found(self, db_session: scoped_session) -> None:
        """Service should return None for missing contact."""
        service = AvisEnqueteService(db_session=db_session)
        result = service.get_contact(99999)
        assert result is None

    def test_get_contact_for_avis(self, db_session: scoped_session) -> None:
        """Service should return contact only if it belongs to the avis."""
        journaliste = User(email="j@test.com")
        expert = User(email="e@test.com")
        media = Organisation(name="Media")
        db_session.add_all([journaliste, expert, media])
        db_session.flush()

        enquete1 = _create_test_enquete(db_session, journaliste, media)
        enquete2 = _create_test_enquete(db_session, journaliste, media)
        contact = _create_test_contact(
            db_session, enquete1, journaliste, expert, StatutAvis.ACCEPTE
        )

        service = AvisEnqueteService(db_session=db_session)

        # Should find contact for correct avis
        result = service.get_contact_for_avis(contact.id, enquete1.id)
        assert result is not None
        assert result.id == contact.id

        # Should not find contact for wrong avis
        result = service.get_contact_for_avis(contact.id, enquete2.id)
        assert result is None

    def test_get_contacts_for_avis(self, db_session: scoped_session) -> None:
        """Service should return all contacts for an avis."""
        journaliste = User(email="j@test.com")
        expert1 = User(email="e1@test.com")
        expert2 = User(email="e2@test.com")
        media = Organisation(name="Media")
        db_session.add_all([journaliste, expert1, expert2, media])
        db_session.flush()

        enquete = _create_test_enquete(db_session, journaliste, media)
        _create_test_contact(
            db_session, enquete, journaliste, expert1, StatutAvis.ACCEPTE
        )
        _create_test_contact(
            db_session, enquete, journaliste, expert2, StatutAvis.EN_ATTENTE
        )

        service = AvisEnqueteService(db_session=db_session)
        results = service.get_contacts_for_avis(enquete.id)

        assert len(results) == 2

    def test_get_contacts_with_rdv(self, db_session: scoped_session) -> None:
        """Service should return only contacts with active RDV."""
        journaliste = User(email="j@test.com")
        expert1 = User(email="e1@test.com")
        expert2 = User(email="e2@test.com")
        media = Organisation(name="Media")
        db_session.add_all([journaliste, expert1, expert2, media])
        db_session.flush()

        enquete = _create_test_enquete(db_session, journaliste, media)
        contact1 = _create_test_contact(
            db_session, enquete, journaliste, expert1, StatutAvis.ACCEPTE
        )
        _create_test_contact(
            db_session, enquete, journaliste, expert2, StatutAvis.ACCEPTE
        )

        # Propose RDV only for contact1
        service = AvisEnqueteService(db_session=db_session)
        future_slot = _get_next_weekday_slot()
        propose_data = RDVProposalData(
            rdv_type=RDVType.PHONE,
            proposed_slots=[future_slot],
            rdv_phone="+33612345678",
        )
        service.propose_rdv(contact1.id, propose_data, "/notification")

        results = service.get_contacts_with_rdv(enquete.id)

        assert len(results) == 1
        assert results[0].id == contact1.id


class TestAvisEnqueteServiceCiblage:
    """Tests for ciblage (expert targeting) methods."""

    def test_store_contacts(self, db_session: scoped_session) -> None:
        """Service should store new contacts for experts."""
        journaliste = User(email="j@test.com")
        expert1 = User(email="e1@test.com")
        expert2 = User(email="e2@test.com")
        media = Organisation(name="Media")
        db_session.add_all([journaliste, expert1, expert2, media])
        db_session.flush()

        enquete = _create_test_enquete(db_session, journaliste, media)

        service = AvisEnqueteService(db_session=db_session)
        contacts = service.store_contacts(enquete, [expert1, expert2])

        assert len(contacts) == 2
        assert all(c.avis_enquete_id == enquete.id for c in contacts)
        assert all(c.journaliste_id == journaliste.id for c in contacts)

    def test_filter_known_experts(self, db_session: scoped_session) -> None:
        """Service should filter out experts who already have contacts."""
        journaliste = User(email="j@test.com")
        expert1 = User(email="e1@test.com")
        expert2 = User(email="e2@test.com")
        expert3 = User(email="e3@test.com")
        media = Organisation(name="Media")
        db_session.add_all([journaliste, expert1, expert2, expert3, media])
        db_session.flush()

        enquete = _create_test_enquete(db_session, journaliste, media)

        # expert1 already has a contact
        _create_test_contact(
            db_session, enquete, journaliste, expert1, StatutAvis.ACCEPTE
        )

        service = AvisEnqueteService(db_session=db_session)
        new_experts = service.filter_known_experts(enquete, [expert1, expert2, expert3])

        # Only expert2 and expert3 should be returned
        assert len(new_experts) == 2
        expert_ids = {e.id for e in new_experts}
        assert expert1.id not in expert_ids
        assert expert2.id in expert_ids
        assert expert3.id in expert_ids


class TestSuggestColleague:
    """Tests for the 'non-mais' suggestion flow (bug #0061)."""

    def _setup(self, db_session):
        journaliste = User(email="j@test.com", active=True)
        # metier_fonction reads from the KYCProfile's JSON fields, so
        # the email-rendering path requires a profile with at least the
        # nested keys it looks up present.
        journaliste.profile = KYCProfile(
            profile_label="Journaliste",
            info_personnelle={"metier_principal_detail": []},
            match_making={"fonctions_journalisme": ["Rédacteur en chef"]},
        )
        media = Organisation(name="Media")
        expert_org = Organisation(name="Strada Transports")
        expert = User(email="expert@test.com", active=True)
        colleague = User(email="colleague@test.com", active=True)
        outsider = User(email="outsider@other.com", active=True)
        other_org = Organisation(name="Other Co")

        db_session.add_all(
            [journaliste, media, expert_org, expert, colleague, outsider, other_org]
        )
        db_session.flush()

        expert.organisation_id = expert_org.id
        colleague.organisation_id = expert_org.id
        outsider.organisation_id = other_org.id
        db_session.flush()

        enquete = _create_test_enquete(db_session, journaliste, media)
        contact = _create_test_contact(
            db_session, enquete, journaliste, expert, StatutAvis.EN_ATTENTE
        )
        return journaliste, expert, colleague, outsider, enquete, contact

    def test_list_eligible_colleagues_returns_org_members(self, db_session) -> None:
        _, _, colleague, outsider, _, contact = self._setup(db_session)

        service = AvisEnqueteService(db_session=db_session)
        eligible = service.list_eligible_colleagues(contact)
        ids = {u.id for u in eligible}

        assert colleague.id in ids
        assert outsider.id not in ids

    def test_list_eligible_colleagues_excludes_self(self, db_session) -> None:
        _, expert, _, _, _, contact = self._setup(db_session)

        service = AvisEnqueteService(db_session=db_session)
        eligible = service.list_eligible_colleagues(contact)
        assert expert.id not in {u.id for u in eligible}

    def test_list_eligible_colleagues_excludes_already_contacted(
        self, db_session
    ) -> None:
        journaliste, _, colleague, _, enquete, contact = self._setup(db_session)
        # Pre-existing contact for colleague → must be filtered out
        _create_test_contact(
            db_session, enquete, journaliste, colleague, StatutAvis.EN_ATTENTE
        )

        service = AvisEnqueteService(db_session=db_session)
        eligible = service.list_eligible_colleagues(contact)
        assert colleague.id not in {u.id for u in eligible}

    def test_list_eligible_colleagues_excludes_inactive(self, db_session) -> None:
        _, _, colleague, _, _, contact = self._setup(db_session)
        colleague.active = False
        db_session.flush()

        service = AvisEnqueteService(db_session=db_session)
        eligible = service.list_eligible_colleagues(contact)
        assert colleague.id not in {u.id for u in eligible}

    def test_suggest_colleague_creates_chained_contact(self, db_session) -> None:
        journaliste, expert, colleague, _, enquete, contact = self._setup(db_session)

        service = AvisEnqueteService(db_session=db_session)
        with patch("app.services.emails.base.EmailMessage"):
            new_contact = service.suggest_colleague(
                contact=contact,
                colleague=colleague,
                url_builder=lambda c: f"/opp/{c.id}",
            )

        assert new_contact.expert_id == colleague.id
        assert new_contact.journaliste_id == journaliste.id
        assert new_contact.avis_enquete_id == enquete.id
        assert new_contact.suggested_by_user_id == expert.id
        assert new_contact.status == StatutAvis.EN_ATTENTE

    def test_suggest_colleague_rejects_outsider(self, db_session) -> None:
        _, _, _, outsider, _, contact = self._setup(db_session)

        service = AvisEnqueteService(db_session=db_session)
        with patch("app.services.emails.base.EmailMessage"):
            with pytest.raises(ValueError, match="not an eligible colleague"):
                service.suggest_colleague(
                    contact=contact,
                    colleague=outsider,
                    url_builder=lambda c: f"/opp/{c.id}",
                )

    def test_suggest_colleague_rejects_self(self, db_session) -> None:
        _, expert, _, _, _, contact = self._setup(db_session)

        service = AvisEnqueteService(db_session=db_session)
        with patch("app.services.emails.base.EmailMessage"):
            with pytest.raises(ValueError, match="not an eligible colleague"):
                service.suggest_colleague(
                    contact=contact,
                    colleague=expert,
                    url_builder=lambda c: f"/opp/{c.id}",
                )

    def test_suggest_colleague_rejects_duplicate(self, db_session) -> None:
        journaliste, _, colleague, _, enquete, contact = self._setup(db_session)
        # Colleague already has a contact for this avis
        _create_test_contact(
            db_session, enquete, journaliste, colleague, StatutAvis.EN_ATTENTE
        )

        service = AvisEnqueteService(db_session=db_session)
        with patch("app.services.emails.base.EmailMessage"):
            with pytest.raises(ValueError, match="not an eligible colleague"):
                service.suggest_colleague(
                    contact=contact,
                    colleague=colleague,
                    url_builder=lambda c: f"/opp/{c.id}",
                )

    def test_suggest_colleague_sends_email_with_suggester_name(
        self, db_session
    ) -> None:
        _, expert, colleague, _, _, contact = self._setup(db_session)
        expert.first_name = "Jocelyne"
        expert.last_name = "Strada"
        db_session.flush()

        service = AvisEnqueteService(db_session=db_session)
        with patch("app.services.emails.base.EmailMessage") as mock_email:
            service.suggest_colleague(
                contact=contact,
                colleague=colleague,
                url_builder=lambda c: f"/opp/{c.id}",
            )

        mock_email.assert_called_once()
        body = mock_email.call_args.kwargs["body"]
        assert "Jocelyne Strada" in body
        assert "collègue de votre organisation" in body
