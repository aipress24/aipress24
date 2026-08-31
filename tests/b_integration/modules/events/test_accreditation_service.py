# Copyright (c) 2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Le service d'accréditation — lot L1, second bloc.

Couvre les règles `RG-03`, `RG-04`, `RG-06` à `RG-11` et `RG-13` de
`specs/events-accreditations.md`, et le plan de test de son §12.

Hors périmètre de ce fichier, faute du champ `audience` qui arrive au
lot L3 : les tests 3, 10b, 10c et 10d, ainsi que `RG-05` — la levée de
la restriction aux journalistes. La livrer avant le ciblage et la
modération ouvrirait l'inscription à tout le monde, immédiate et sans
recours pour l'organisateur, ce qui est pire que l'état actuel.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import arrow
import pytest
from sqlalchemy import event as sa_event

from app.models.auth import User
from app.models.lifecycle import PublicationStatus
from app.modules.events.models import Accreditation, AccreditationStatus, EventPost
from app.modules.events.services import (
    AccreditationClosedError,
    accept_accreditations,
    get_accreditation,
    get_accreditations_by_status,
    get_participants,
    reject_accreditations,
    request_accreditation,
    withdraw_accreditation,
)

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


@pytest.fixture
def organiser(db_session: Session) -> User:
    user = User(email="svc-organiser@example.com")
    user.photo = b""
    user.active = True
    db_session.add(user)
    db_session.flush()
    return user


@pytest.fixture
def event(db_session: Session, organiser: User) -> EventPost:
    post = EventPost(title="Salon L1", owner=organiser)
    post.status = PublicationStatus.PUBLIC
    post.start_datetime = arrow.utcnow().shift(days=7)
    post.end_datetime = arrow.utcnow().shift(days=7, hours=3)
    db_session.add(post)
    db_session.flush()
    return post


def _member(db_session: Session, n: int = 0) -> User:
    user = User(email=f"svc-member-{n}@example.com")
    user.photo = b""
    user.active = True
    db_session.add(user)
    db_session.flush()
    return user


@pytest.fixture
def member(db_session: Session) -> User:
    return _member(db_session)


def _count(db_session: Session, event: EventPost) -> int:
    return len(
        db_session.query(Accreditation).filter(Accreditation.event_id == event.id).all()
    )


class TestRequest:
    def test_creates_a_requested_row(
        self, db_session: Session, event: EventPost, member: User
    ) -> None:
        row = request_accreditation(event, member)
        db_session.flush()

        assert row.status == AccreditationStatus.REQUESTED
        assert _count(db_session, event) == 1

    def test_second_call_is_a_no_op(
        self, db_session: Session, event: EventPost, member: User
    ) -> None:
        """RG-10 — deux clics ne créent qu'une ligne, et le second ne
        lève pas : il renvoie l'état courant."""
        first = request_accreditation(event, member)
        db_session.flush()
        second = request_accreditation(event, member)
        db_session.flush()

        assert second.id == first.id
        assert _count(db_session, event) == 1

    def test_refused_once_the_event_has_started(
        self, db_session: Session, event: EventPost, member: User
    ) -> None:
        """RG-04 — la porte se ferme au début de l'événement."""
        event.start_datetime = arrow.utcnow().shift(hours=-1)
        db_session.flush()

        with pytest.raises(AccreditationClosedError):
            request_accreditation(event, member)
        assert _count(db_session, event) == 0

    def test_refused_on_an_unpublished_event(
        self, db_session: Session, event: EventPost, member: User
    ) -> None:
        event.status = PublicationStatus.DRAFT
        db_session.flush()

        with pytest.raises(AccreditationClosedError):
            request_accreditation(event, member)

    def test_any_member_may_request_when_untargeted(
        self, db_session: Session, event: EventPost, member: User
    ) -> None:
        """Test 4 du §12 — sans ciblage, l'événement est ouvert."""
        assert request_accreditation(event, member) is not None


class TestDecision:
    def test_accept_records_the_decision(
        self, db_session: Session, event: EventPost, member: User, organiser: User
    ) -> None:
        request_accreditation(event, member)
        db_session.flush()

        accept_accreditations(event, [member.id], decided_by=organiser)
        db_session.flush()

        row = get_accreditation(event, member)
        assert row is not None
        assert row.status == AccreditationStatus.ACCEPTED
        assert row.decided_at is not None
        assert row.decided_by_id == organiser.id

    def test_reject_records_the_decision(
        self, db_session: Session, event: EventPost, member: User, organiser: User
    ) -> None:
        request_accreditation(event, member)
        db_session.flush()

        reject_accreditations(event, [member.id], decided_by=organiser)
        db_session.flush()

        row = get_accreditation(event, member)
        assert row is not None
        assert row.status == AccreditationStatus.REJECTED

    def test_organiser_may_withdraw_an_accreditation(
        self, db_session: Session, event: EventPost, member: User, organiser: User
    ) -> None:
        """RG-09 — retrait d'une accréditation déjà accordée."""
        request_accreditation(event, member)
        accept_accreditations(event, [member.id], decided_by=organiser)
        db_session.flush()

        reject_accreditations(event, [member.id], decided_by=organiser)
        db_session.flush()

        row = get_accreditation(event, member)
        assert row is not None
        assert row.status == AccreditationStatus.REJECTED

    def test_organiser_may_reopen_a_refusal(
        self, db_session: Session, event: EventPost, member: User, organiser: User
    ) -> None:
        """RG-13 — « Accréditer finalement ». C'est la seule sortie de
        REJECTED, et elle n'appartient qu'à l'organisateur."""
        request_accreditation(event, member)
        reject_accreditations(event, [member.id], decided_by=organiser)
        db_session.flush()

        accept_accreditations(event, [member.id], decided_by=organiser)
        db_session.flush()

        row = get_accreditation(event, member)
        assert row is not None
        assert row.status == AccreditationStatus.ACCEPTED

    def test_bulk_accept_issues_a_single_update(
        self, db_session: Session, event: EventPost, organiser: User
    ) -> None:
        """Test 12 du §12 — l'écran organisateur accrédite par lot ;
        une requête par ligne ne passerait pas l'échelle."""
        members = [_member(db_session, n) for n in range(1, 6)]
        for m in members:
            request_accreditation(event, m)
        db_session.flush()

        updates: list[str] = []

        def record(conn, cursor, statement, *args) -> None:
            if statement.lstrip().upper().startswith("UPDATE"):
                updates.append(statement)

        engine = db_session.get_bind()
        sa_event.listen(engine, "after_cursor_execute", record)
        try:
            accept_accreditations(event, [m.id for m in members], decided_by=organiser)
            db_session.flush()
        finally:
            sa_event.remove(engine, "after_cursor_execute", record)

        assert len(updates) == 1, f"attendu 1 UPDATE, obtenu {len(updates)}"
        accepted = get_accreditations_by_status(event, AccreditationStatus.ACCEPTED)
        assert len(accepted) == 5


class TestWithdrawal:
    @pytest.mark.parametrize(
        "reach_state",
        ["requested", "accepted"],
    )
    def test_member_withdraws_from_either_state(
        self,
        db_session: Session,
        event: EventPost,
        member: User,
        organiser: User,
        reach_state: str,
    ) -> None:
        """RG-08 — annuler sa demande et se désinscrire sont le même
        geste côté membre."""
        request_accreditation(event, member)
        if reach_state == "accepted":
            accept_accreditations(event, [member.id], decided_by=organiser)
        db_session.flush()

        withdraw_accreditation(event, member)
        db_session.flush()

        row = get_accreditation(event, member)
        assert row is not None
        assert row.status == AccreditationStatus.WITHDRAWN

    def test_may_request_again_after_withdrawing(
        self, db_session: Session, event: EventPost, member: User
    ) -> None:
        request_accreditation(event, member)
        withdraw_accreditation(event, member)
        db_session.flush()

        row = request_accreditation(event, member)
        db_session.flush()

        assert row.status == AccreditationStatus.REQUESTED
        assert _count(db_session, event) == 1

    def test_may_not_request_again_after_a_refusal(
        self, db_session: Session, event: EventPost, member: User, organiser: User
    ) -> None:
        """RG-03 / D5 — un refus est définitif côté membre, sans quoi
        rien n'empêche le harcèlement par re-demandes."""
        request_accreditation(event, member)
        reject_accreditations(event, [member.id], decided_by=organiser)
        db_session.flush()

        row = request_accreditation(event, member)
        db_session.flush()

        assert row.status == AccreditationStatus.REJECTED
        assert _count(db_session, event) == 1

    def test_withdrawing_without_a_request_is_a_no_op(
        self, db_session: Session, event: EventPost, member: User
    ) -> None:
        assert withdraw_accreditation(event, member) is None
        assert _count(db_session, event) == 0


class TestParticipants:
    def test_only_accepted_members_are_participants(
        self, db_session: Session, event: EventPost, organiser: User
    ) -> None:
        """RG-11 — le bloc public « Participants » ne montre que les
        accrédités, jamais les demandes en cours ni les refus."""
        accepted, requested, rejected, withdrawn = (
            _member(db_session, n) for n in (10, 11, 12, 13)
        )
        for m in (accepted, requested, rejected, withdrawn):
            request_accreditation(event, m)
        accept_accreditations(event, [accepted.id], decided_by=organiser)
        reject_accreditations(event, [rejected.id], decided_by=organiser)
        withdraw_accreditation(event, withdrawn)
        db_session.flush()

        ids = {u.id for u in get_participants(event)}
        assert ids == {accepted.id}


class TestDecisionsAreScoped:
    """Une décision ne touche et ne prévient que des lignes légitimes.

    Trois défauts trouvés en revue tenaient tous à l'absence de garde
    sur `_decide` : n'importe quel identifiant posté dans le formulaire
    recevait cloche et email, et un `WITHDRAWN` pouvait être ressuscité
    en `ACCEPTED` — une arête que la machine à états n'a pas.
    """

    def test_an_id_that_never_requested_is_ignored(
        self, db_session: Session, event: EventPost, organiser: User
    ) -> None:
        """POST forgé : l'identifiant d'un membre sans demande."""
        stranger = _member(db_session, 90)

        touched = accept_accreditations(event, [stranger.id], decided_by=organiser)
        db_session.flush()

        assert touched == 0
        assert get_accreditation(event, stranger) is None

    def test_a_withdrawn_member_is_not_revived(
        self, db_session: Session, event: EventPost, member: User, organiser: User
    ) -> None:
        """Seul le membre sort de WITHDRAWN, en re-demandant."""
        request_accreditation(event, member)
        withdraw_accreditation(event, member)
        db_session.flush()

        assert accept_accreditations(event, [member.id], decided_by=organiser) == 0
        db_session.flush()

        assert get_accreditation(event, member).status == (
            AccreditationStatus.WITHDRAWN
        )

    def test_a_refusal_cannot_be_laundered_through_withdrawal(
        self, db_session: Session, event: EventPost, member: User, organiser: User
    ) -> None:
        """Sans garde, « se retirer » d'un refus le transformait en
        WITHDRAWN, que RG-03 laisse re-demander — et le harcèlement par
        re-demandes que D5 interdit redevenait possible."""
        request_accreditation(event, member)
        reject_accreditations(event, [member.id], decided_by=organiser)
        db_session.flush()

        withdraw_accreditation(event, member)
        db_session.flush()
        assert get_accreditation(event, member).status == (AccreditationStatus.REJECTED)

        request_accreditation(event, member)
        db_session.flush()
        assert get_accreditation(event, member).status == (AccreditationStatus.REJECTED)
