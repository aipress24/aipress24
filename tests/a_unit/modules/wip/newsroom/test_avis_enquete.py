# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from datetime import datetime

import arrow
import pytest
from sqlalchemy.orm import scoped_session

from app.models.auth import User
from app.models.organisation import Organisation
from app.modules.wip.models.newsroom.avis_enquete import (
    AvisEnquete,
    ContactAvisEnquete,
    RDVStatus,
    RDVType,
    StatutAvis,
)


def test_avis_enquete(db_session: scoped_session) -> None:
    assert isinstance(db_session, scoped_session)

    joe = User(email="joe@example.com")
    jim = User(email="jim@example.com")

    media = Organisation(name="Le Journal")

    db_session.add_all([joe, jim, media])
    db_session.flush()

    enquete = AvisEnquete()
    enquete.owner = joe
    enquete.media = media

    # FIXME
    enquete.commanditaire_id = jim.id

    enquete.date_debut_enquete = arrow.get("2022-01-01").datetime
    enquete.date_fin_enquete = arrow.get("2022-01-01").datetime
    enquete.date_bouclage = arrow.get("2022-01-01").datetime
    enquete.date_parution_prevue = arrow.get("2022-01-01").datetime

    db_session.add(enquete)
    db_session.flush()


def test_rdv_workflow_business_logic(db_session: scoped_session) -> None:
    """Test complete RDV workflow using business methods"""
    # Setup: Create users
    journaliste = User(email="j@media.com")
    expert = User(email="e@example.com")
    media = Organisation(name="Le Figaro")

    db_session.add_all([journaliste, expert, media])
    db_session.flush()

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

    contact = ContactAvisEnquete(
        avis_enquete_id=enquete.id,
        journaliste_id=journaliste.id,
        expert_id=expert.id,
        status=StatutAvis.ACCEPTE,
        date_reponse=datetime.now(),
    )
    db_session.add(contact)
    db_session.flush()

    # BUSINESS RULE: Can only propose RDV if expert has accepted
    assert contact.can_propose_rdv() is True

    # BUSINESS RULE: Propose RDV with validation
    proposed_slots = [
        "2025-01-15T10:00",
        "2025-01-15T14:00",
        "2025-01-16T09:00",
    ]

    contact.propose_rdv(
        rdv_type=RDVType.VIDEO,
        proposed_slots=proposed_slots,
        rdv_video_link="https://meet.google.com/abc-defg-hij",
        rdv_notes="Nous discuterons des impacts de l'IA",
    )

    assert contact.rdv_status == RDVStatus.PROPOSED
    assert contact.rdv_type == RDVType.VIDEO
    assert len(contact.proposed_slots) == 3
    assert contact.can_accept_rdv() is True

    # BUSINESS RULE: Expert accepts a proposed slot
    selected_slot = proposed_slots[1]
    contact.accept_rdv(selected_slot, expert_notes="J'ai hâte d'en discuter")

    assert contact.rdv_status == RDVStatus.ACCEPTED
    assert contact.date_rdv.strftime("%Y-%m-%dT%H:%M") == selected_slot
    assert contact.rdv_notes_expert == "J'ai hâte d'en discuter"

    # BUSINESS RULE: Can confirm after acceptance
    assert contact.can_confirm_rdv() is True
    contact.confirm_rdv()
    assert contact.rdv_status == RDVStatus.CONFIRMED


def test_rdv_proposal_validation(db_session: scoped_session) -> None:
    """Test business rules for RDV proposal validation"""
    journaliste = User(email="j@test.com")
    expert = User(email="e@test.com")
    media = Organisation(name="Media")

    db_session.add_all([journaliste, expert, media])
    db_session.flush()

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

    contact = ContactAvisEnquete(
        avis_enquete_id=enquete.id,
        journaliste_id=journaliste.id,
        expert_id=expert.id,
        status=StatutAvis.EN_ATTENTE,  # NOT ACCEPTED
    )
    db_session.add(contact)
    db_session.flush()

    # BUSINESS RULE: Cannot propose RDV if expert hasn't accepted
    assert contact.can_propose_rdv() is False

    with pytest.raises(ValueError, match="expert has not accepted"):
        contact.propose_rdv(
            rdv_type=RDVType.PHONE,
            proposed_slots=["2025-01-15T10:00"],
        )

    # Accept the enquête
    contact.status = StatutAvis.ACCEPTE
    assert contact.can_propose_rdv() is True

    # BUSINESS RULE: Must provide at least one slot
    with pytest.raises(ValueError, match="At least one time slot"):
        contact.propose_rdv(rdv_type=RDVType.PHONE, proposed_slots=[])

    # BUSINESS RULE: Maximum 5 slots
    with pytest.raises(ValueError, match="Maximum 5 time slots"):
        contact.propose_rdv(
            rdv_type=RDVType.PHONE,
            proposed_slots=[f"2025-01-{i:02d}T10:00" for i in range(15, 22)],
        )

    # BUSINESS RULE: Slots must be valid ISO format
    with pytest.raises(ValueError, match="Invalid slot format"):
        contact.propose_rdv(
            rdv_type=RDVType.PHONE,
            proposed_slots=["not-a-valid-date"],
        )

    # Valid proposal should work
    contact.propose_rdv(
        rdv_type=RDVType.PHONE,
        proposed_slots=["2025-01-15T10:00"],
        rdv_phone="+33 6 12 34 56 78",
    )
    assert contact.rdv_status == RDVStatus.PROPOSED

    # BUSINESS RULE: Cannot propose again if RDV already exists
    assert contact.can_propose_rdv() is False
    with pytest.raises(ValueError, match="RDV already exists"):
        contact.propose_rdv(
            rdv_type=RDVType.VIDEO,
            proposed_slots=["2025-01-16T14:00"],
        )


def test_rdv_acceptance_validation(db_session: scoped_session) -> None:
    """Test business rules for RDV acceptance"""
    journaliste = User(email="j@test.com")
    expert = User(email="e@test.com")
    media = Organisation(name="Media")

    db_session.add_all([journaliste, expert, media])
    db_session.flush()

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

    contact = ContactAvisEnquete(
        avis_enquete_id=enquete.id,
        journaliste_id=journaliste.id,
        expert_id=expert.id,
        status=StatutAvis.ACCEPTE,
    )
    db_session.add(contact)
    db_session.flush()

    # BUSINESS RULE: Cannot accept if no RDV proposed
    assert contact.can_accept_rdv() is False
    with pytest.raises(ValueError, match="no RDV has been proposed"):
        contact.accept_rdv("2025-01-15T10:00")

    # Propose a RDV
    proposed_slots = [
        "2025-01-15T10:00",
        "2025-01-15T14:00",
        "2025-01-16T09:00",
    ]
    contact.propose_rdv(
        rdv_type=RDVType.VIDEO,
        proposed_slots=proposed_slots,
    )

    # BUSINESS RULE: Selected slot must be in proposed slots
    with pytest.raises(ValueError, match="must be one of the proposed slots"):
        contact.accept_rdv("2025-01-20T10:00")

    # BUSINESS RULE: Slot must be valid format
    with pytest.raises(ValueError, match="Invalid slot format"):
        contact.accept_rdv("invalid-date")

    # Valid acceptance
    contact.accept_rdv(proposed_slots[1], expert_notes="Perfect timing")
    assert contact.rdv_status == RDVStatus.ACCEPTED
    assert contact.date_rdv.strftime("%Y-%m-%dT%H:%M") == proposed_slots[1]
    assert contact.rdv_notes_expert == "Perfect timing"


def test_rdv_cancellation(db_session: scoped_session) -> None:
    """Test RDV cancellation business logic"""
    journaliste = User(email="j@test.com")
    expert = User(email="e@test.com")
    media = Organisation(name="Media")

    db_session.add_all([journaliste, expert, media])
    db_session.flush()

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

    contact = ContactAvisEnquete(
        avis_enquete_id=enquete.id,
        journaliste_id=journaliste.id,
        expert_id=expert.id,
        status=StatutAvis.ACCEPTE,
    )
    db_session.add(contact)
    db_session.flush()

    # BUSINESS RULE: Cannot cancel if no RDV exists
    with pytest.raises(ValueError, match="No RDV to cancel"):
        contact.cancel_rdv()

    # Propose and accept a RDV
    contact.propose_rdv(
        rdv_type=RDVType.PHONE,
        proposed_slots=["2025-01-15T10:00"],
        rdv_phone="+33 6 12 34 56 78",
    )
    contact.accept_rdv("2025-01-15T10:00")

    assert contact.rdv_status == RDVStatus.ACCEPTED
    assert contact.date_rdv is not None

    # Cancel the RDV
    contact.cancel_rdv()

    # Verify state is reset
    assert contact.rdv_status == RDVStatus.NO_RDV
    assert contact.rdv_type is None
    assert contact.proposed_slots == []
    assert contact.date_rdv is None
    assert contact.rdv_phone == ""
    assert contact.rdv_notes_journaliste == ""
    assert contact.rdv_notes_expert == ""

    # Can propose again after cancellation
    assert contact.can_propose_rdv() is True
