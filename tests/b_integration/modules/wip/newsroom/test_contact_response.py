# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Tests for ContactAvisEnquete response functionality."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

import arrow
import pytest

from app.models.auth import User
from app.models.organisation import Organisation
from app.modules.wip.models.newsroom.avis_enquete import (
    AvisEnquete,
    ContactAvisEnquete,
    RDVStatus,
    StatutAvis,
)

if TYPE_CHECKING:
    from sqlalchemy.orm import scoped_session


# ----------------------------------------------------------------
# Fixtures
# ----------------------------------------------------------------


@pytest.fixture
def journaliste(db_session: scoped_session) -> User:
    """Create a test journalist user."""
    user = User(email="j@test.com")
    db_session.add(user)
    db_session.flush()
    return user


@pytest.fixture
def expert(db_session: scoped_session) -> User:
    """Create a test expert user."""
    user = User(email="e@test.com")
    db_session.add(user)
    db_session.flush()
    return user


@pytest.fixture
def media(db_session: scoped_session) -> Organisation:
    """Create a test media organisation."""
    org = Organisation(name="Media")
    db_session.add(org)
    db_session.flush()
    return org


@pytest.fixture
def enquete(
    db_session: scoped_session, journaliste: User, media: Organisation
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


@pytest.fixture
def contact(
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

    def test_initial_status_is_en_attente(self, contact: ContactAvisEnquete) -> None:
        """The initial status is EN_ATTENTE."""
        assert contact.status == StatutAvis.EN_ATTENTE

    def test_initial_date_reponse_is_none(self, contact: ContactAvisEnquete) -> None:
        """The response date is None initially."""
        assert contact.date_reponse is None

    def test_initial_rdv_status_is_no_rdv(self, contact: ContactAvisEnquete) -> None:
        """The RDV status is NO_RDV initially."""
        assert contact.rdv_status == RDVStatus.NO_RDV

    def test_cannot_propose_rdv_initially(self, contact: ContactAvisEnquete) -> None:
        """Cannot propose RDV when contact is in EN_ATTENTE status."""
        assert contact.can_propose_rdv() is False


# ----------------------------------------------------------------
# Accept Tests
# ----------------------------------------------------------------


class TestContactAccept:
    """Tests for accepting an avis."""

    def test_accept_changes_status(self, contact: ContactAvisEnquete) -> None:
        """Setting status to ACCEPTE changes the status."""
        contact.status = StatutAvis.ACCEPTE
        contact.date_reponse = datetime.now(UTC)

        assert contact.status == StatutAvis.ACCEPTE

    def test_accept_sets_date_reponse(self, contact: ContactAvisEnquete) -> None:
        """Accepting sets the response date."""
        now = datetime.now(UTC)
        contact.status = StatutAvis.ACCEPTE
        contact.date_reponse = now

        assert contact.date_reponse is not None
        assert contact.date_reponse == now

    def test_accept_enables_rdv_proposal(self, contact: ContactAvisEnquete) -> None:
        """After accepting, can_propose_rdv() returns True."""
        # Initially cannot propose
        assert contact.can_propose_rdv() is False

        # Accept the avis
        contact.status = StatutAvis.ACCEPTE
        contact.date_reponse = datetime.now(UTC)

        # Now can propose RDV
        assert contact.can_propose_rdv() is True


# ----------------------------------------------------------------
# Refuse Tests
# ----------------------------------------------------------------


class TestContactRefuse:
    """Tests for refusing an avis."""

    def test_refuse_changes_status(self, contact: ContactAvisEnquete) -> None:
        """Setting status to REFUSE changes the status."""
        contact.status = StatutAvis.REFUSE
        contact.date_reponse = datetime.now(UTC)

        assert contact.status == StatutAvis.REFUSE

    def test_refuse_sets_date_reponse(self, contact: ContactAvisEnquete) -> None:
        """Refusing sets the response date."""
        now = datetime.now(UTC)
        contact.status = StatutAvis.REFUSE
        contact.date_reponse = now

        assert contact.date_reponse is not None
        assert contact.date_reponse == now

    def test_refuse_disables_rdv_proposal(self, contact: ContactAvisEnquete) -> None:
        """After refusing, can_propose_rdv() returns False."""
        contact.status = StatutAvis.REFUSE
        contact.date_reponse = datetime.now(UTC)

        # Cannot propose RDV to refused contact
        assert contact.can_propose_rdv() is False


# ----------------------------------------------------------------
# Refuse With Suggestion Tests
# ----------------------------------------------------------------


class TestContactRefuseWithSuggestion:
    """Tests for refusing with a suggestion."""

    def test_refuse_with_suggestion_changes_status(
        self, contact: ContactAvisEnquete
    ) -> None:
        """Status becomes REFUSE_SUGGESTION."""
        contact.status = StatutAvis.REFUSE_SUGGESTION
        contact.date_reponse = datetime.now(UTC)

        assert contact.status == StatutAvis.REFUSE_SUGGESTION

    def test_refuse_suggestion_disables_rdv_proposal(
        self, contact: ContactAvisEnquete
    ) -> None:
        """After refusing with suggestion, can_propose_rdv() returns False."""
        contact.status = StatutAvis.REFUSE_SUGGESTION
        contact.date_reponse = datetime.now(UTC)

        # Cannot propose RDV
        assert contact.can_propose_rdv() is False


# ----------------------------------------------------------------
# Status Transitions Tests
# ----------------------------------------------------------------


class TestStatusTransitions:
    """Tests for status transition behavior."""

    def test_all_statuses_are_valid(self, contact: ContactAvisEnquete) -> None:
        """All StatutAvis values can be assigned."""
        for status in StatutAvis:
            contact.status = status
            assert contact.status == status

    def test_only_accepte_enables_rdv(self, contact: ContactAvisEnquete) -> None:
        """Only ACCEPTE status enables RDV proposal."""
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

    def test_contact_links_to_avis_enquete(
        self, contact: ContactAvisEnquete, enquete: AvisEnquete
    ) -> None:
        """Contact is linked to its AvisEnquete."""
        assert contact.avis_enquete_id == enquete.id
        assert contact.avis_enquete == enquete

    def test_contact_links_to_journaliste(
        self, contact: ContactAvisEnquete, journaliste: User
    ) -> None:
        """Contact is linked to the journalist."""
        assert contact.journaliste_id == journaliste.id
        assert contact.journaliste == journaliste

    def test_contact_links_to_expert(
        self, contact: ContactAvisEnquete, expert: User
    ) -> None:
        """Contact is linked to the expert."""
        assert contact.expert_id == expert.id
        assert contact.expert == expert
