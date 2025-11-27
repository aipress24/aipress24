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
    # Generate future weekday slots
    from datetime import timedelta, timezone

    now = datetime.now(timezone.utc)
    days_ahead = 1
    while (now + timedelta(days=days_ahead)).weekday() >= 5:
        days_ahead += 1
    base_date = now + timedelta(days=days_ahead)

    # Find the next weekday after base_date for the third slot
    next_weekday = base_date + timedelta(days=1)
    while next_weekday.weekday() >= 5:
        next_weekday += timedelta(days=1)

    proposed_slots = [
        base_date.replace(hour=10, minute=0, second=0, microsecond=0),
        base_date.replace(hour=14, minute=0, second=0, microsecond=0),
        next_weekday.replace(hour=9, minute=0, second=0, microsecond=0),
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
    assert contact.date_rdv == selected_slot
    assert contact.rdv_notes_expert == "J'ai hâte d'en discuter"

    # BUSINESS RULE: Can confirm after acceptance
    assert contact.can_confirm_rdv() is True
    contact.confirm_rdv()
    assert contact.rdv_status == RDVStatus.CONFIRMED


def test_rdv_proposal_validation(db_session: scoped_session) -> None:
    """Test business rules for RDV proposal validation"""
    from datetime import datetime, timedelta, timezone

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

    # Generate dynamic future slots
    now = datetime.now(timezone.utc)
    days_ahead = 1
    while (now + timedelta(days=days_ahead)).weekday() >= 5:
        days_ahead += 1
    future_slot = (now + timedelta(days=days_ahead)).replace(
        hour=10, minute=0, second=0, microsecond=0
    )

    # BUSINESS RULE: Cannot propose RDV if expert hasn't accepted
    assert contact.can_propose_rdv() is False

    with pytest.raises(ValueError, match="expert has not accepted"):
        contact.propose_rdv(
            rdv_type=RDVType.PHONE,
            proposed_slots=[future_slot],
        )

    # Accept the enquête
    contact.status = StatutAvis.ACCEPTE
    assert contact.can_propose_rdv() is True

    # BUSINESS RULE: Must provide at least one slot
    with pytest.raises(ValueError, match="At least one time slot"):
        contact.propose_rdv(rdv_type=RDVType.PHONE, proposed_slots=[])

    # BUSINESS RULE: Maximum 5 slots
    many_slots = [
        (now + timedelta(days=days_ahead + i)).replace(
            hour=10, minute=0, second=0, microsecond=0
        )
        for i in range(7)
    ]
    with pytest.raises(ValueError, match="Maximum 5 time slots"):
        contact.propose_rdv(
            rdv_type=RDVType.PHONE,
            proposed_slots=many_slots,
        )

    # Valid proposal should work
    contact.propose_rdv(
        rdv_type=RDVType.PHONE,
        proposed_slots=[future_slot],
        rdv_phone="+33 6 12 34 56 78",
    )
    assert contact.rdv_status == RDVStatus.PROPOSED

    # BUSINESS RULE: Cannot propose again if RDV already exists
    assert contact.can_propose_rdv() is False
    another_slot = (now + timedelta(days=days_ahead + 1)).replace(
        hour=14, minute=0, second=0, microsecond=0
    )
    with pytest.raises(ValueError, match="RDV already exists"):
        contact.propose_rdv(
            rdv_type=RDVType.VIDEO,
            proposed_slots=[another_slot],
        )


def test_rdv_acceptance_validation(db_session: scoped_session) -> None:
    """Test business rules for RDV acceptance"""
    from datetime import datetime, timedelta, timezone

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

    # Generate dynamic future slots
    now = datetime.now(timezone.utc)
    days_ahead = 1
    while (now + timedelta(days=days_ahead)).weekday() >= 5:
        days_ahead += 1
    base_date = now + timedelta(days=days_ahead)

    # BUSINESS RULE: Cannot accept if no RDV proposed
    assert contact.can_accept_rdv() is False
    invalid_slot = base_date.replace(hour=10, minute=0, second=0, microsecond=0)
    with pytest.raises(ValueError, match="no RDV has been proposed"):
        contact.accept_rdv(invalid_slot)

    # Propose a RDV - ensure all slots are on weekdays
    next_weekday = base_date + timedelta(days=1)
    while next_weekday.weekday() >= 5:
        next_weekday += timedelta(days=1)

    proposed_slots = [
        base_date.replace(hour=10, minute=0, second=0, microsecond=0),
        base_date.replace(hour=14, minute=0, second=0, microsecond=0),
        next_weekday.replace(hour=9, minute=0, second=0, microsecond=0),
    ]
    contact.propose_rdv(
        rdv_type=RDVType.VIDEO,
        proposed_slots=proposed_slots,
        rdv_video_link="https://meet.google.com/test",
    )

    # BUSINESS RULE: Selected slot must be in proposed slots
    wrong_slot = (base_date + timedelta(days=5)).replace(
        hour=10, minute=0, second=0, microsecond=0
    )
    with pytest.raises(ValueError, match="must be one of the proposed slots"):
        contact.accept_rdv(wrong_slot)

    # Valid acceptance
    contact.accept_rdv(proposed_slots[1], expert_notes="Perfect timing")
    assert contact.rdv_status == RDVStatus.ACCEPTED
    assert contact.date_rdv == proposed_slots[1]
    assert contact.rdv_notes_expert == "Perfect timing"


def test_rdv_cancellation(db_session: scoped_session) -> None:
    """Test RDV cancellation business logic"""
    from datetime import datetime, timedelta, timezone

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

    # Generate dynamic future slot
    now = datetime.now(timezone.utc)
    days_ahead = 1
    while (now + timedelta(days=days_ahead)).weekday() >= 5:
        days_ahead += 1
    future_slot = (now + timedelta(days=days_ahead)).replace(
        hour=10, minute=0, second=0, microsecond=0
    )

    # Propose and accept a RDV
    contact.propose_rdv(
        rdv_type=RDVType.PHONE,
        proposed_slots=[future_slot],
        rdv_phone="+33 6 12 34 56 78",
    )
    contact.accept_rdv(future_slot)

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


def test_rdv_temporal_validation(db_session: scoped_session) -> None:
    """Test temporal validation for RDV slots"""
    from datetime import datetime, timedelta, timezone

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

    # BUSINESS RULE: Cannot propose slot in the past
    past_slot = datetime.now(timezone.utc) - timedelta(hours=1)
    with pytest.raises(ValueError, match="must be in the future"):
        contact.propose_rdv(
            rdv_type=RDVType.PHONE,
            proposed_slots=[past_slot],
            rdv_phone="+33612345678",
        )

    # BUSINESS RULE: Cannot propose slot outside business hours (before 9h)
    early_morning = (datetime.now(timezone.utc) + timedelta(days=1)).replace(
        hour=7, minute=0
    )
    with pytest.raises(ValueError, match="business hours"):
        contact.propose_rdv(
            rdv_type=RDVType.PHONE,
            proposed_slots=[early_morning],
            rdv_phone="+33612345678",
        )

    # BUSINESS RULE: Cannot propose slot outside business hours (after 18h)
    late_evening = (datetime.now(timezone.utc) + timedelta(days=1)).replace(
        hour=19, minute=0
    )
    with pytest.raises(ValueError, match="business hours"):
        contact.propose_rdv(
            rdv_type=RDVType.PHONE,
            proposed_slots=[late_evening],
            rdv_phone="+33612345678",
        )

    # BUSINESS RULE: Cannot propose slot on weekend
    # Find next Saturday
    now = datetime.now(timezone.utc)
    days_until_saturday = (5 - now.weekday()) % 7
    if days_until_saturday == 0:
        days_until_saturday = 7
    next_saturday = (now + timedelta(days=days_until_saturday)).replace(
        hour=10, minute=0
    )
    with pytest.raises(ValueError, match="cannot be on weekend"):
        contact.propose_rdv(
            rdv_type=RDVType.PHONE,
            proposed_slots=[next_saturday],
            rdv_phone="+33612345678",
        )


def test_rdv_type_coordinates_validation(db_session: scoped_session) -> None:
    """Test validation of RDV type matching required coordinates"""
    from datetime import datetime, timedelta, timezone

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

    # Get a valid future weekday slot at 10h
    now = datetime.now(timezone.utc)
    # Find next weekday
    days_ahead = 1
    while (now + timedelta(days=days_ahead)).weekday() >= 5:
        days_ahead += 1
    future_slot = (now + timedelta(days=days_ahead)).replace(
        hour=10, minute=0, second=0, microsecond=0
    )

    # BUSINESS RULE: PHONE type requires phone number
    with pytest.raises(ValueError, match="Phone number required"):
        contact.propose_rdv(
            rdv_type=RDVType.PHONE,
            proposed_slots=[future_slot],
            # Missing rdv_phone
        )

    # BUSINESS RULE: VIDEO type requires video link
    with pytest.raises(ValueError, match="Video link required"):
        contact.propose_rdv(
            rdv_type=RDVType.VIDEO,
            proposed_slots=[future_slot],
            # Missing rdv_video_link
        )

    # BUSINESS RULE: F2F type requires address
    with pytest.raises(ValueError, match="Address required"):
        contact.propose_rdv(
            rdv_type=RDVType.F2F,
            proposed_slots=[future_slot],
            # Missing rdv_address
        )

    # Valid proposals should work
    contact.propose_rdv(
        rdv_type=RDVType.PHONE,
        proposed_slots=[future_slot],
        rdv_phone="+33612345678",
    )
    assert contact.rdv_status == RDVStatus.PROPOSED


def test_rdv_query_methods(db_session: scoped_session) -> None:
    """Test query methods for RDV state"""
    from datetime import datetime, timedelta, timezone

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

    # Initial state: no RDV
    assert contact.has_rdv is False
    assert contact.is_rdv_confirmed is False
    assert contact.is_waiting_expert_response is False
    assert contact.get_rdv_summary() == "Pas de rendez-vous"

    # Get valid future slot
    now = datetime.now(timezone.utc)
    days_ahead = 1
    while (now + timedelta(days=days_ahead)).weekday() >= 5:
        days_ahead += 1
    future_slot = (now + timedelta(days=days_ahead)).replace(
        hour=10, minute=0, second=0, microsecond=0
    )

    # Propose RDV
    contact.propose_rdv(
        rdv_type=RDVType.VIDEO,
        proposed_slots=[future_slot],
        rdv_video_link="https://meet.google.com/abc",
    )

    # After proposal
    assert contact.has_rdv is True
    assert contact.is_rdv_confirmed is False
    assert contact.is_waiting_expert_response is True
    assert "RDV proposé (1 créneaux)" in contact.get_rdv_summary()

    # Accept RDV
    contact.accept_rdv(future_slot)

    # After acceptance
    assert contact.has_rdv is True
    assert contact.is_rdv_confirmed is False
    assert contact.is_waiting_expert_response is False
    assert "RDV Visio le" in contact.get_rdv_summary()

    # Confirm RDV
    contact.confirm_rdv()

    # After confirmation
    assert contact.has_rdv is True
    assert contact.is_rdv_confirmed is True
    assert contact.is_waiting_expert_response is False


def test_rdv_temporal_calculations(db_session: scoped_session) -> None:
    """Test temporal calculations for RDV"""
    from datetime import datetime, timedelta, timezone

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

    # No RDV: temporal methods return None/False
    assert contact.time_until_rdv() is None
    assert contact.is_rdv_soon is False
    assert contact.is_rdv_past is False

    # Create RDV "soon" (within 24h) - must be in future and business hours
    now = datetime.now(timezone.utc)

    # Try to find a time within next few hours that's in business hours
    target_time = now + timedelta(hours=1)

    # Ensure business hours (9h-18h) and weekday
    if target_time.hour < 9:
        target_time = target_time.replace(hour=10, minute=0, second=0, microsecond=0)
    elif target_time.hour >= 17:
        # Too late today, move to tomorrow morning
        target_time = (target_time + timedelta(days=1)).replace(
            hour=10, minute=0, second=0, microsecond=0
        )

    # Skip weekends
    while target_time.weekday() >= 5:
        target_time = target_time + timedelta(days=1)

    # Verify it's within 24h (if not, skip this assertion)
    time_until = target_time - now
    is_within_24h = time_until <= timedelta(hours=24)

    contact.propose_rdv(
        rdv_type=RDVType.PHONE,
        proposed_slots=[target_time],
        rdv_phone="+33612345678",
    )
    contact.accept_rdv(target_time)

    # RDV timing checks
    time_delta = contact.time_until_rdv()
    assert time_delta is not None
    assert time_delta > timedelta(0)
    assert contact.is_rdv_past is False

    # Only assert is_rdv_soon if we managed to create one within 24h
    if is_within_24h:
        assert contact.is_rdv_soon is True
    else:
        assert contact.is_rdv_soon is False

    # Create RDV far in future (not soon)
    contact.cancel_rdv()
    far_future = (now + timedelta(days=30)).replace(
        hour=10, minute=0, second=0, microsecond=0
    )
    # Ensure weekday
    while far_future.weekday() >= 5:
        far_future += timedelta(days=1)

    contact.propose_rdv(
        rdv_type=RDVType.PHONE,
        proposed_slots=[far_future],
        rdv_phone="+33612345678",
    )
    contact.accept_rdv(far_future)

    # RDV is not soon (> 24h away)
    assert contact.time_until_rdv() > timedelta(hours=24)
    assert contact.is_rdv_soon is False
    assert contact.is_rdv_past is False
