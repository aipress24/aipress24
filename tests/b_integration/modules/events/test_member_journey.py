# Copyright (c) 2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Le parcours du membre — lot L2, §7.1 et §8 de
`specs/events-accreditations.md`.

Le bouton « S'accréditer », qui accréditait d'un clic, devient
« Demande d'accréditation » : le membre demande, l'organisateur décide.
C'est le basculement du modèle ouvert et immédiat vers le modèle ciblé
et modéré, et il n'a de sens qu'une fois l'écran organisateur livré
(lot L4), sans quoi les demandes s'empileraient sans issue.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import arrow
import pytest
from flask import g
from sqlalchemy import event as sa_event

from app.enums import CommunityEnum, RoleEnum
from app.models.auth import Role, User
from app.models.lifecycle import PublicationStatus
from app.modules.events.models import AccreditationStatus, EventPost
from app.modules.events.services import (
    accept_accreditations,
    accredited_ids_among,
    get_accreditation,
    request_accreditation,
    sees_full_content,
)
from app.modules.events.views.event_detail import EventDetailView

if TYPE_CHECKING:
    from flask import Flask
    from sqlalchemy.orm import Session


def _role(db_session: Session, role_enum: RoleEnum) -> Role:
    existing = db_session.query(Role).filter_by(name=role_enum.name).first()
    if existing is not None:
        return existing
    role = Role(name=role_enum.name, description=role_enum.value)
    db_session.add(role)
    db_session.flush()
    return role


def _user(db_session: Session, tag: str, role: RoleEnum | None = None) -> User:
    user = User(email=f"mj-{tag}@example.com", first_name=tag.title())
    user.photo = b""
    user.active = True
    if role is not None:
        user.roles.append(_role(db_session, role))
    db_session.add(user)
    db_session.flush()
    return user


@pytest.fixture
def organiser(db_session: Session) -> User:
    return _user(db_session, "organiser")


@pytest.fixture
def event(db_session: Session, organiser: User) -> EventPost:
    post = EventPost(title="Salon parcours", owner=organiser)
    post.status = PublicationStatus.PUBLIC
    post.start_datetime = arrow.utcnow().shift(days=5)
    db_session.add(post)
    db_session.flush()
    return post


@pytest.fixture
def member(db_session: Session) -> User:
    return _user(db_session, "member", RoleEnum.PRESS_MEDIA)


class TestTheSixDisplayStates:
    """§7.1 — ce que voit le membre selon l'état de sa demande."""

    def _status(self, event: EventPost, user: User) -> AccreditationStatus | None:
        row = get_accreditation(event, user)
        return row.status if row is not None else None

    def test_no_request_yet(
        self, db_session: Session, event: EventPost, member: User
    ) -> None:
        assert self._status(event, member) is None

    def test_request_pending(
        self, db_session: Session, event: EventPost, member: User
    ) -> None:
        request_accreditation(event, member)
        db_session.flush()
        assert self._status(event, member) == AccreditationStatus.REQUESTED

    def test_accredited(
        self,
        db_session: Session,
        event: EventPost,
        member: User,
        organiser: User,
    ) -> None:
        request_accreditation(event, member)
        accept_accreditations(event, [member.id], decided_by=organiser)
        db_session.flush()
        assert self._status(event, member) == AccreditationStatus.ACCEPTED


class TestContentVisibility:
    """RG-01 / RG-02 — le ciblage restreint le contenu, pas l'existence."""

    def test_member_outside_the_audience_does_not_see_the_content(
        self, db_session: Session, event: EventPost
    ) -> None:
        event.audience = [CommunityEnum.PRESS_MEDIA.value]
        db_session.flush()
        academic = _user(db_session, "academic", RoleEnum.ACADEMIC)

        assert sees_full_content(academic, event) is False

    def test_targeted_member_sees_it(
        self, db_session: Session, event: EventPost, member: User
    ) -> None:
        event.audience = [CommunityEnum.PRESS_MEDIA.value]
        db_session.flush()

        assert sees_full_content(member, event) is True

    def test_the_organiser_always_sees_their_own_event(
        self, db_session: Session, event: EventPost, organiser: User
    ) -> None:
        """10d — sans quoi un organisateur ne pourrait plus relire son
        annonce dès qu'il cible une communauté dont il n'est pas."""
        event.audience = [CommunityEnum.ACADEMICS.value]
        db_session.flush()

        assert sees_full_content(organiser, event) is True

    def test_an_administrator_always_sees_the_content(
        self, db_session: Session, event: EventPost
    ) -> None:
        """10d — sinon le support ne peut plus instruire un signalement."""
        event.audience = [CommunityEnum.PRESS_MEDIA.value]
        db_session.flush()
        admin = _user(db_session, "admin", RoleEnum.ADMIN)

        assert sees_full_content(admin, event) is True


class TestPostActions:
    """§8 — le dispatcher reçoit deux actions ; `toggle-participate`
    disparaît."""

    def test_requesting_then_withdrawing(
        self, app: Flask, db_session: Session, event: EventPost, member: User
    ) -> None:
        view = EventDetailView()
        with app.test_request_context():
            g.user = member
            view._request_accreditation(member, event)
            db_session.flush()
            assert get_accreditation(event, member).status == (
                AccreditationStatus.REQUESTED
            )

            view._withdraw_accreditation(member, event)
            db_session.flush()
            assert get_accreditation(event, member).status == (
                AccreditationStatus.WITHDRAWN
            )

    def test_outside_the_audience_is_refused(
        self, app: Flask, db_session: Session, event: EventPost
    ) -> None:
        event.audience = [CommunityEnum.PRESS_MEDIA.value]
        db_session.flush()
        academic = _user(db_session, "academic2", RoleEnum.ACADEMIC)

        view = EventDetailView()
        with app.test_request_context():
            g.user = academic
            response = view._request_accreditation(academic, event)

        assert response.status_code == 403
        assert get_accreditation(event, academic) is None

    def test_a_started_event_refuses_with_409(
        self, app: Flask, db_session: Session, event: EventPost, member: User
    ) -> None:
        """RG-04 — la porte se ferme au début de l'événement."""
        event.start_datetime = arrow.utcnow().shift(hours=-1)
        db_session.flush()

        view = EventDetailView()
        with app.test_request_context():
            g.user = member
            response = view._request_accreditation(member, event)

        assert response.status_code == 409
        assert get_accreditation(event, member) is None


class TestListDoesNotQueryPerCard:
    """Test 17 du §12 — la pastille « Accrédité.e » ne vaut pas une
    requête par carte."""

    def test_one_query_for_the_whole_page(
        self,
        db_session: Session,
        organiser: User,
        member: User,
    ) -> None:
        posts = []
        for n in range(6):
            post = EventPost(title=f"Salon {n}", owner=organiser)
            post.status = PublicationStatus.PUBLIC
            post.start_datetime = arrow.utcnow().shift(days=n + 1)
            db_session.add(post)
            posts.append(post)
        db_session.flush()
        request_accreditation(posts[0], member)
        accept_accreditations(posts[0], [member.id], decided_by=organiser)
        db_session.flush()

        selects: list[str] = []

        def record(conn, cursor, statement, *args) -> None:
            if "evt_accreditation" in statement.lower():
                selects.append(statement)

        engine = db_session.get_bind()
        sa_event.listen(engine, "after_cursor_execute", record)
        try:
            accredited = accredited_ids_among(member, [p.id for p in posts])
        finally:
            sa_event.remove(engine, "after_cursor_execute", record)

        assert accredited == {posts[0].id}
        assert len(selects) == 1, f"attendu 1 requête, obtenu {len(selects)}"

    def test_an_anonymous_visitor_costs_no_query(self) -> None:
        assert accredited_ids_among(None, [1, 2, 3]) == set()
