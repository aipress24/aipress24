# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from datetime import datetime

import arrow
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


def test_rdv_workflow(db_session: scoped_session) -> None:
    """Test complete RDV workflow: propose -> accept"""
    # Setup: Create users
    journaliste = User(
        email="journaliste@media.com",
        first_name="Alice",
        last_name="Martin",
    )
    expert = User(
        email="expert@example.com",
        first_name="Bob",
        last_name="Dupont",
    )
    media = Organisation(name="Le Figaro")

    db_session.add_all([journaliste, expert, media])
    db_session.flush()

    # Create an Avis d'Enquête
    enquete = AvisEnquete(
        owner=journaliste,
        media=media,
        titre="Enquête sur l'IA",
        commanditaire_id=journaliste.id,
        date_debut_enquete=arrow.get("2025-01-01").datetime,
        date_fin_enquete=arrow.get("2025-02-01").datetime,
        date_bouclage=arrow.get("2025-02-15").datetime,
        date_parution_prevue=arrow.get("2025-03-01").datetime,
    )

    db_session.add(enquete)
    db_session.flush()

    # Create a ContactAvisEnquete (expert accepted the enquête)
    contact = ContactAvisEnquete(
        avis_enquete_id=enquete.id,
        journaliste_id=journaliste.id,
        expert_id=expert.id,
        status=StatutAvis.ACCEPTE,
        date_reponse=datetime.now(),
    )

    db_session.add(contact)
    db_session.flush()

    # Test initial state
    assert contact.rdv_status == RDVStatus.NO_RDV
    assert contact.rdv_type is None
    assert contact.proposed_slots == []
    assert contact.date_rdv is None

    # Step 1: Journalist proposes RDV
    proposed_slots = [
        "2025-01-15T10:00",
        "2025-01-15T14:00",
        "2025-01-16T09:00",
    ]

    contact.rdv_type = RDVType.VIDEO
    contact.rdv_status = RDVStatus.PROPOSED
    contact.proposed_slots = proposed_slots
    contact.rdv_video_link = "https://meet.google.com/abc-defg-hij"
    contact.rdv_notes_journaliste = "Nous discuterons des impacts de l'IA"

    db_session.flush()

    # Verify proposal
    assert contact.rdv_status == RDVStatus.PROPOSED
    assert contact.rdv_type == RDVType.VIDEO
    assert len(contact.proposed_slots) == 3
    assert contact.rdv_video_link == "https://meet.google.com/abc-defg-hij"
    assert contact.rdv_notes_journaliste == "Nous discuterons des impacts de l'IA"

    # Step 2: Expert accepts a slot
    selected_slot = proposed_slots[1]  # Second slot
    contact.rdv_status = RDVStatus.ACCEPTED
    contact.date_rdv = datetime.fromisoformat(selected_slot)
    contact.rdv_notes_expert = "J'ai hâte d'en discuter"

    db_session.flush()

    # Verify acceptance
    assert contact.rdv_status == RDVStatus.ACCEPTED
    assert contact.date_rdv is not None
    assert contact.date_rdv.strftime("%Y-%m-%dT%H:%M") == selected_slot
    assert contact.rdv_notes_expert == "J'ai hâte d'en discuter"

    # Verify we can retrieve the contact from database
    retrieved_contact = db_session.query(ContactAvisEnquete).get(contact.id)
    assert retrieved_contact is not None
    assert retrieved_contact.rdv_status == RDVStatus.ACCEPTED
    assert retrieved_contact.rdv_type == RDVType.VIDEO
    assert retrieved_contact.date_rdv.strftime("%Y-%m-%dT%H:%M") == selected_slot


def test_rdv_types(db_session: scoped_session) -> None:
    """Test different RDV types with appropriate contact details"""
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

    # Test PHONE type
    contact_phone = ContactAvisEnquete(
        avis_enquete_id=enquete.id,
        journaliste_id=journaliste.id,
        expert_id=expert.id,
        status=StatutAvis.ACCEPTE,
        rdv_type=RDVType.PHONE,
        rdv_phone="+33 6 12 34 56 78",
    )
    db_session.add(contact_phone)

    # Test VIDEO type
    contact_video = ContactAvisEnquete(
        avis_enquete_id=enquete.id,
        journaliste_id=journaliste.id,
        expert_id=expert.id,
        status=StatutAvis.ACCEPTE,
        rdv_type=RDVType.VIDEO,
        rdv_video_link="https://zoom.us/j/123456789",
    )
    db_session.add(contact_video)

    # Test F2F type
    contact_f2f = ContactAvisEnquete(
        avis_enquete_id=enquete.id,
        journaliste_id=journaliste.id,
        expert_id=expert.id,
        status=StatutAvis.ACCEPTE,
        rdv_type=RDVType.F2F,
        rdv_address="123 rue de la République, 75001 Paris",
    )
    db_session.add(contact_f2f)

    db_session.flush()

    # Verify
    assert contact_phone.rdv_type == RDVType.PHONE
    assert contact_phone.rdv_phone == "+33 6 12 34 56 78"

    assert contact_video.rdv_type == RDVType.VIDEO
    assert contact_video.rdv_video_link == "https://zoom.us/j/123456789"

    assert contact_f2f.rdv_type == RDVType.F2F
    assert contact_f2f.rdv_address == "123 rue de la République, 75001 Paris"


def test_rdv_status_transitions(db_session: scoped_session) -> None:
    """Test RDV status transitions: NO_RDV -> PROPOSED -> ACCEPTED -> CONFIRMED"""
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

    # Initial state
    assert contact.rdv_status == RDVStatus.NO_RDV

    # Transition to PROPOSED
    contact.rdv_status = RDVStatus.PROPOSED
    contact.proposed_slots = ["2025-01-15T10:00"]
    db_session.flush()
    assert contact.rdv_status == RDVStatus.PROPOSED

    # Transition to ACCEPTED
    contact.rdv_status = RDVStatus.ACCEPTED
    contact.date_rdv = datetime.fromisoformat("2025-01-15T10:00")
    db_session.flush()
    assert contact.rdv_status == RDVStatus.ACCEPTED

    # Transition to CONFIRMED (optional step)
    contact.rdv_status = RDVStatus.CONFIRMED
    db_session.flush()
    assert contact.rdv_status == RDVStatus.CONFIRMED
