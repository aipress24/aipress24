# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Tests for ContactAvisEnquete response functionality."""

from __future__ import annotations

from datetime import datetime, timezone

import arrow
from app.models.auth import User
from app.models.organisation import Organisation
from app.modules.wip.models.newsroom.avis_enquete import (
    AvisEnquete,
    ContactAvisEnquete,
    RDVStatus,
    StatutAvis,
)
from sqlalchemy.orm import scoped_session


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
) -> ContactAvisEnquete:
    """Create a test ContactAvisEnquete with default values."""
    contact = ContactAvisEnquete(
        avis_enquete_id=enquete.id,
        journaliste_id=journaliste.id,
        expert_id=expert.id,
    )
    db_session.add(contact)
    db_session.flush()
    return contact


# ----------------------------------------------------------------
# Initial State Tests
# ----------------------------------------------------------------


class TestContactInitialState:
    """Tests for the initial state of a contact."""

    def test_initial_status_is_en_attente(self, db_session: scoped_session) -> None:
        """The initial status is EN_ATTENTE."""
        journaliste = User(email="j@test.com")
        expert = User(email="e@test.com")
        media = Organisation(name="Media")
        db_session.add_all([journaliste, expert, media])
        db_session.flush()

        enquete = _create_test_enquete(db_session, journaliste, media)
        contact = _create_test_contact(db_session, enquete, journaliste, expert)

        assert contact.status == StatutAvis.EN_ATTENTE

    def test_initial_date_reponse_is_none(self, db_session: scoped_session) -> None:
        """The response date is None initially."""
        journaliste = User(email="j@test.com")
        expert = User(email="e@test.com")
        media = Organisation(name="Media")
        db_session.add_all([journaliste, expert, media])
        db_session.flush()

        enquete = _create_test_enquete(db_session, journaliste, media)
        contact = _create_test_contact(db_session, enquete, journaliste, expert)

        assert contact.date_reponse is None

    def test_initial_rdv_status_is_no_rdv(self, db_session: scoped_session) -> None:
        """The RDV status is NO_RDV initially."""
        journaliste = User(email="j@test.com")
        expert = User(email="e@test.com")
        media = Organisation(name="Media")
        db_session.add_all([journaliste, expert, media])
        db_session.flush()

        enquete = _create_test_enquete(db_session, journaliste, media)
        contact = _create_test_contact(db_session, enquete, journaliste, expert)

        assert contact.rdv_status == RDVStatus.NO_RDV

    def test_cannot_propose_rdv_initially(self, db_session: scoped_session) -> None:
        """Cannot propose RDV when contact is in EN_ATTENTE status."""
        journaliste = User(email="j@test.com")
        expert = User(email="e@test.com")
        media = Organisation(name="Media")
        db_session.add_all([journaliste, expert, media])
        db_session.flush()

        enquete = _create_test_enquete(db_session, journaliste, media)
        contact = _create_test_contact(db_session, enquete, journaliste, expert)

        assert contact.can_propose_rdv() is False


# ----------------------------------------------------------------
# Accept Tests
# ----------------------------------------------------------------


class TestContactAccept:
    """Tests for accepting an avis."""

    def test_accept_changes_status(self, db_session: scoped_session) -> None:
        """Setting status to ACCEPTE changes the status."""
        journaliste = User(email="j@test.com")
        expert = User(email="e@test.com")
        media = Organisation(name="Media")
        db_session.add_all([journaliste, expert, media])
        db_session.flush()

        enquete = _create_test_enquete(db_session, journaliste, media)
        contact = _create_test_contact(db_session, enquete, journaliste, expert)

        # Accept the avis
        contact.status = StatutAvis.ACCEPTE
        contact.date_reponse = datetime.now(timezone.utc)

        assert contact.status == StatutAvis.ACCEPTE

    def test_accept_sets_date_reponse(self, db_session: scoped_session) -> None:
        """Accepting sets the response date."""
        journaliste = User(email="j@test.com")
        expert = User(email="e@test.com")
        media = Organisation(name="Media")
        db_session.add_all([journaliste, expert, media])
        db_session.flush()

        enquete = _create_test_enquete(db_session, journaliste, media)
        contact = _create_test_contact(db_session, enquete, journaliste, expert)

        # Accept the avis with timestamp
        now = datetime.now(timezone.utc)
        contact.status = StatutAvis.ACCEPTE
        contact.date_reponse = now

        assert contact.date_reponse is not None
        assert contact.date_reponse == now

    def test_accept_enables_rdv_proposal(self, db_session: scoped_session) -> None:
        """After accepting, can_propose_rdv() returns True."""
        journaliste = User(email="j@test.com")
        expert = User(email="e@test.com")
        media = Organisation(name="Media")
        db_session.add_all([journaliste, expert, media])
        db_session.flush()

        enquete = _create_test_enquete(db_session, journaliste, media)
        contact = _create_test_contact(db_session, enquete, journaliste, expert)

        # Initially cannot propose
        assert contact.can_propose_rdv() is False

        # Accept the avis
        contact.status = StatutAvis.ACCEPTE
        contact.date_reponse = datetime.now(timezone.utc)

        # Now can propose RDV
        assert contact.can_propose_rdv() is True


# ----------------------------------------------------------------
# Refuse Tests
# ----------------------------------------------------------------


class TestContactRefuse:
    """Tests for refusing an avis."""

    def test_refuse_changes_status(self, db_session: scoped_session) -> None:
        """Setting status to REFUSE changes the status."""
        journaliste = User(email="j@test.com")
        expert = User(email="e@test.com")
        media = Organisation(name="Media")
        db_session.add_all([journaliste, expert, media])
        db_session.flush()

        enquete = _create_test_enquete(db_session, journaliste, media)
        contact = _create_test_contact(db_session, enquete, journaliste, expert)

        # Refuse the avis
        contact.status = StatutAvis.REFUSE
        contact.date_reponse = datetime.now(timezone.utc)

        assert contact.status == StatutAvis.REFUSE

    def test_refuse_sets_date_reponse(self, db_session: scoped_session) -> None:
        """Refusing sets the response date."""
        journaliste = User(email="j@test.com")
        expert = User(email="e@test.com")
        media = Organisation(name="Media")
        db_session.add_all([journaliste, expert, media])
        db_session.flush()

        enquete = _create_test_enquete(db_session, journaliste, media)
        contact = _create_test_contact(db_session, enquete, journaliste, expert)

        # Refuse with timestamp
        now = datetime.now(timezone.utc)
        contact.status = StatutAvis.REFUSE
        contact.date_reponse = now

        assert contact.date_reponse is not None
        assert contact.date_reponse == now

    def test_refuse_disables_rdv_proposal(self, db_session: scoped_session) -> None:
        """After refusing, can_propose_rdv() returns False."""
        journaliste = User(email="j@test.com")
        expert = User(email="e@test.com")
        media = Organisation(name="Media")
        db_session.add_all([journaliste, expert, media])
        db_session.flush()

        enquete = _create_test_enquete(db_session, journaliste, media)
        contact = _create_test_contact(db_session, enquete, journaliste, expert)

        # Refuse the avis
        contact.status = StatutAvis.REFUSE
        contact.date_reponse = datetime.now(timezone.utc)

        # Cannot propose RDV to refused contact
        assert contact.can_propose_rdv() is False


# ----------------------------------------------------------------
# Refuse With Suggestion Tests
# ----------------------------------------------------------------


class TestContactRefuseWithSuggestion:
    """Tests for refusing with a suggestion."""

    def test_refuse_with_suggestion_changes_status(
        self, db_session: scoped_session
    ) -> None:
        """Status becomes REFUSE_SUGGESTION."""
        journaliste = User(email="j@test.com")
        expert = User(email="e@test.com")
        media = Organisation(name="Media")
        db_session.add_all([journaliste, expert, media])
        db_session.flush()

        enquete = _create_test_enquete(db_session, journaliste, media)
        contact = _create_test_contact(db_session, enquete, journaliste, expert)

        # Refuse with suggestion
        contact.status = StatutAvis.REFUSE_SUGGESTION
        contact.date_reponse = datetime.now(timezone.utc)

        assert contact.status == StatutAvis.REFUSE_SUGGESTION

    def test_refuse_suggestion_disables_rdv_proposal(
        self, db_session: scoped_session
    ) -> None:
        """After refusing with suggestion, can_propose_rdv() returns False."""
        journaliste = User(email="j@test.com")
        expert = User(email="e@test.com")
        media = Organisation(name="Media")
        db_session.add_all([journaliste, expert, media])
        db_session.flush()

        enquete = _create_test_enquete(db_session, journaliste, media)
        contact = _create_test_contact(db_session, enquete, journaliste, expert)

        # Refuse with suggestion
        contact.status = StatutAvis.REFUSE_SUGGESTION
        contact.date_reponse = datetime.now(timezone.utc)

        # Cannot propose RDV
        assert contact.can_propose_rdv() is False


# ----------------------------------------------------------------
# Status Transitions Tests
# ----------------------------------------------------------------


class TestStatusTransitions:
    """Tests for status transition behavior."""

    def test_all_statuses_are_valid(self, db_session: scoped_session) -> None:
        """All StatutAvis values can be assigned."""
        journaliste = User(email="j@test.com")
        expert = User(email="e@test.com")
        media = Organisation(name="Media")
        db_session.add_all([journaliste, expert, media])
        db_session.flush()

        enquete = _create_test_enquete(db_session, journaliste, media)
        contact = _create_test_contact(db_session, enquete, journaliste, expert)

        # All statuses should be assignable
        for status in StatutAvis:
            contact.status = status
            assert contact.status == status

    def test_only_accepte_enables_rdv(self, db_session: scoped_session) -> None:
        """Only ACCEPTE status enables RDV proposal."""
        journaliste = User(email="j@test.com")
        expert = User(email="e@test.com")
        media = Organisation(name="Media")
        db_session.add_all([journaliste, expert, media])
        db_session.flush()

        enquete = _create_test_enquete(db_session, journaliste, media)
        contact = _create_test_contact(db_session, enquete, journaliste, expert)

        # Test each status
        for status in StatutAvis:
            contact.status = status
            contact.rdv_status = RDVStatus.NO_RDV  # Reset RDV status
            if status in {StatutAvis.ACCEPTE, StatutAvis.ACCEPTE_RELATION_PRESSE}:
                assert contact.can_propose_rdv() is True
            else:
                assert contact.can_propose_rdv() is False


# ----------------------------------------------------------------
# Relationship Tests
# ----------------------------------------------------------------


class TestContactRelationships:
    """Tests for contact relationships."""

    def test_contact_links_to_avis_enquete(self, db_session: scoped_session) -> None:
        """Contact is linked to its AvisEnquete."""
        journaliste = User(email="j@test.com")
        expert = User(email="e@test.com")
        media = Organisation(name="Media")
        db_session.add_all([journaliste, expert, media])
        db_session.flush()

        enquete = _create_test_enquete(db_session, journaliste, media)
        contact = _create_test_contact(db_session, enquete, journaliste, expert)

        assert contact.avis_enquete_id == enquete.id
        assert contact.avis_enquete == enquete

    def test_contact_links_to_journaliste(self, db_session: scoped_session) -> None:
        """Contact is linked to the journalist."""
        journaliste = User(email="j@test.com")
        expert = User(email="e@test.com")
        media = Organisation(name="Media")
        db_session.add_all([journaliste, expert, media])
        db_session.flush()

        enquete = _create_test_enquete(db_session, journaliste, media)
        contact = _create_test_contact(db_session, enquete, journaliste, expert)

        assert contact.journaliste_id == journaliste.id
        assert contact.journaliste == journaliste

    def test_contact_links_to_expert(self, db_session: scoped_session) -> None:
        """Contact is linked to the expert."""
        journaliste = User(email="j@test.com")
        expert = User(email="e@test.com")
        media = Organisation(name="Media")
        db_session.add_all([journaliste, expert, media])
        db_session.flush()

        enquete = _create_test_enquete(db_session, journaliste, media)
        contact = _create_test_contact(db_session, enquete, journaliste, expert)

        assert contact.expert_id == expert.id
        assert contact.expert == expert
