# Copyright (c) 2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Le modèle `Accreditation` — lot L1, premier bloc.

`evt_participation` était une table de jointure sans état : on y était
ou on n'y était pas. Le workflow d'accréditation (`EVT-42` à `EVT-47`)
demande un état par couple (événement, membre), avec une décision
datée et son auteur.

Ce fichier épingle le contrat du modèle. Les règles de transition
(`RG-03` à `RG-13`) et le service qui les applique arrivent au second
bloc ; ici on vérifie seulement ce que la base garantit : une ligne par
couple, un statut par défaut, une décision facultative.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import arrow
import pytest
from sqlalchemy.exc import IntegrityError

from app.models.auth import User
from app.modules.events.models import (
    Accreditation,
    AccreditationStatus,
    EventPost,
)

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


@pytest.fixture
def owner(db_session: Session) -> User:
    user = User(email="accred-owner@example.com")
    user.photo = b""
    user.active = True
    db_session.add(user)
    db_session.flush()
    return user


@pytest.fixture
def event(db_session: Session, owner: User) -> EventPost:
    post = EventPost(title="Conférence L1", owner=owner)
    db_session.add(post)
    db_session.flush()
    return post


@pytest.fixture
def member(db_session: Session) -> User:
    user = User(email="accred-member@example.com")
    user.photo = b""
    user.active = True
    db_session.add(user)
    db_session.flush()
    return user


class TestAccreditationModel:
    def test_defaults_to_requested(
        self, db_session: Session, event: EventPost, member: User
    ) -> None:
        row = Accreditation(event_id=event.id, user_id=member.id)
        db_session.add(row)
        db_session.flush()
        db_session.refresh(row)

        assert row.status == AccreditationStatus.REQUESTED
        assert row.requested_at is not None
        assert row.decided_at is None
        assert row.decided_by_id is None

    def test_one_row_per_event_and_member(
        self, db_session: Session, event: EventPost, member: User
    ) -> None:
        """L'unicité est portée par la base, pas par le service : deux
        demandes concurrentes ne peuvent pas créer deux lignes."""
        db_session.add(Accreditation(event_id=event.id, user_id=member.id))
        db_session.flush()

        db_session.add(Accreditation(event_id=event.id, user_id=member.id))
        with pytest.raises(IntegrityError):
            db_session.flush()
        db_session.rollback()

    def test_decision_is_recorded_with_its_author(
        self, db_session: Session, event: EventPost, member: User, owner: User
    ) -> None:
        row = Accreditation(event_id=event.id, user_id=member.id)
        db_session.add(row)
        db_session.flush()

        row.status = AccreditationStatus.ACCEPTED
        row.decided_at = arrow.utcnow()
        row.decided_by_id = owner.id
        db_session.flush()
        db_session.refresh(row)

        assert row.status == AccreditationStatus.ACCEPTED
        assert row.decided_by_id == owner.id

    @pytest.mark.parametrize("status", list(AccreditationStatus))
    def test_every_status_round_trips(
        self, db_session: Session, event: EventPost, member: User, status
    ) -> None:
        row = Accreditation(event_id=event.id, user_id=member.id, status=status)
        db_session.add(row)
        db_session.flush()
        db_session.refresh(row)

        assert row.status is status

    def test_relationships_resolve(
        self, db_session: Session, event: EventPost, member: User
    ) -> None:
        row = Accreditation(event_id=event.id, user_id=member.id)
        db_session.add(row)
        db_session.flush()

        assert row.event.id == event.id
        assert row.user.id == member.id
