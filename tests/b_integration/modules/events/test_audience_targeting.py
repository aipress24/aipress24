# Copyright (c) 2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Ciblage d'un événement par communauté — lot L3.

Règles `RG-03a`, `RG-03b` et `RG-05` de `specs/events-accreditations.md`.
Reprend les tests 3, 6, 10b, 10c et 10d de son §12, laissés en attente
au lot L1 faute du champ `audience`.

`RG-05` arrive ici et non au L1 : lever la restriction aux journalistes
avant qu'un ciblage ne la remplace ouvrirait l'inscription à tout le
monde sans recours pour l'organisateur.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import arrow
import pytest
from flask import g, render_template

from app.enums import CommunityEnum, RoleEnum
from app.models.auth import Role, User
from app.models.lifecycle import PublicationStatus
from app.modules.events.models import EventPost
from app.modules.events.services import (
    AccreditationClosedError,
    in_audience,
    request_accreditation,
    sees_access_details,
    sees_full_content,
)
from app.modules.events.views._common import EventDetailVM

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


def _role(db_session: Session, role_enum: RoleEnum) -> Role:
    existing = db_session.query(Role).filter_by(name=role_enum.name).first()
    if existing is not None:
        return existing
    role = Role(name=role_enum.name, description=role_enum.value)
    db_session.add(role)
    db_session.flush()
    return role


def _member(db_session: Session, tag: str, role_enum: RoleEnum | None = None) -> User:
    user = User(email=f"aud-{tag}@example.com")
    user.photo = b""
    user.active = True
    if role_enum is not None:
        user.roles.append(_role(db_session, role_enum))
    db_session.add(user)
    db_session.flush()
    return user


@pytest.fixture
def organiser(db_session: Session) -> User:
    return _member(db_session, "organiser")


@pytest.fixture
def event(db_session: Session, organiser: User) -> EventPost:
    post = EventPost(title="Conférence de presse", owner=organiser)
    post.status = PublicationStatus.PUBLIC
    post.start_datetime = arrow.utcnow().shift(days=7)
    db_session.add(post)
    db_session.flush()
    return post


class TestInAudience:
    """RG-03a — l'appartenance se calcule sur les rôles, via
    `COMMUNITY_TO_ROLE`. Jamais via `User.first_community()`, qui lève
    `RuntimeError` sur un compte sans rôle de communauté."""

    def test_empty_audience_is_open_to_everyone(self, db_session: Session) -> None:
        assert in_audience(_member(db_session, "anyone"), []) is True

    def test_member_of_a_targeted_community_passes(self, db_session: Session) -> None:
        journalist = _member(db_session, "journo", RoleEnum.PRESS_MEDIA)
        assert in_audience(journalist, [CommunityEnum.PRESS_MEDIA.value]) is True

    def test_member_of_another_community_is_refused(self, db_session: Session) -> None:
        expert = _member(db_session, "expert", RoleEnum.EXPERT)
        assert in_audience(expert, [CommunityEnum.PRESS_MEDIA.value]) is False

    def test_member_without_any_community_role_raises_nothing(
        self, db_session: Session
    ) -> None:
        """Test 10c — le piège `first_community()`. Un administrateur
        ou un compte de service n'a aucun rôle de communauté ; il doit
        être refusé, pas faire planter la page."""
        nobody = _member(db_session, "nobody")

        assert in_audience(nobody, [CommunityEnum.PRESS_MEDIA.value]) is False
        assert in_audience(nobody, []) is True

    def test_several_communities_are_a_disjunction(self, db_session: Session) -> None:
        expert = _member(db_session, "expert2", RoleEnum.EXPERT)
        targeted = [
            CommunityEnum.PRESS_MEDIA.value,
            CommunityEnum.LEADERS_EXPERTS.value,
        ]
        assert in_audience(expert, targeted) is True


class TestRequestIsGatedOnAudience:
    def test_targeted_member_may_request(
        self, db_session: Session, event: EventPost
    ) -> None:
        event.audience = [CommunityEnum.PRESS_MEDIA.value]
        db_session.flush()
        journalist = _member(db_session, "journo2", RoleEnum.PRESS_MEDIA)

        assert request_accreditation(event, journalist) is not None

    def test_member_outside_the_audience_is_refused(
        self, db_session: Session, event: EventPost
    ) -> None:
        """Test 3 du §12 — hors audience, pas de demande possible."""
        event.audience = [CommunityEnum.PRESS_MEDIA.value]
        db_session.flush()
        expert = _member(db_session, "expert3", RoleEnum.EXPERT)

        with pytest.raises(PermissionError):
            request_accreditation(event, expert)

    def test_untargeted_event_stays_open_to_all(
        self, db_session: Session, event: EventPost
    ) -> None:
        expert = _member(db_session, "expert4", RoleEnum.EXPERT)
        assert request_accreditation(event, expert) is not None

    def test_audience_does_not_reopen_a_closed_event(
        self, db_session: Session, event: EventPost
    ) -> None:
        """Le ciblage s'ajoute aux conditions de RG-03, il ne s'y
        substitue pas."""
        event.start_datetime = arrow.utcnow().shift(hours=-1)
        db_session.flush()
        journalist = _member(db_session, "journo3", RoleEnum.PRESS_MEDIA)

        with pytest.raises(AccreditationClosedError):
            request_accreditation(event, journalist)


class TestRoleRestrictionIsLifted:
    """RG-05 / écart E1 — le livré réservait l'inscription aux
    journalistes sur **tous** les événements, y compris un salon ouvert
    ou un webinaire académique. Aucune spécification ne le demandait."""

    def test_a_non_journalist_may_register_for_an_untargeted_event(
        self, db_session: Session, event: EventPost
    ) -> None:
        """Test 6 du §12 — non-régression de l'écart E1."""
        academic = _member(db_session, "academic", RoleEnum.ACADEMIC)
        assert in_audience(academic, event.audience or []) is True

    def test_a_press_event_still_restricts_to_journalists(
        self, db_session: Session, event: EventPost
    ) -> None:
        event.audience = [CommunityEnum.PRESS_MEDIA.value]
        db_session.flush()

        journalist = _member(db_session, "journo4", RoleEnum.PRESS_MEDIA)
        academic = _member(db_session, "academic2", RoleEnum.ACADEMIC)

        assert in_audience(journalist, event.audience or []) is True
        assert in_audience(academic, event.audience or []) is False


class TestTheGuardsActuallyBite:
    """Les tests d'origine vérifiaient chaque moitié séparément — le
    prédicat d'un côté, l'écran de l'autre — et aucun ne traversait le
    pont. Deux défauts s'y cachaient : le contenu restait servi à tous,
    et cibler un événement publié ne changeait rien.
    """

    def test_the_page_hides_its_content_from_outsiders(
        self, app, db_session: Session, event: EventPost, organiser: User
    ) -> None:
        """RG-02 — le prédicat ne suffit pas, encore faut-il que le
        gabarit le consomme."""
        event.content = "Le secret de la conférence"
        event.audience = [CommunityEnum.PRESS_MEDIA.value]
        db_session.flush()
        outsider = _member(db_session, "outsider", RoleEnum.ACADEMIC)

        with app.test_request_context("/"):
            g.user = outsider
            html = render_template(
                "pages/event--main.j2",
                event=EventDetailVM(event),
                sees_content=sees_full_content(outsider, event),
                sees_access_details=sees_access_details(outsider, event),
                audience=event.audience,
            )

        assert "Le secret de la conférence" not in html
        assert "réservé aux communautés" in html

    def test_the_page_shows_its_content_to_the_audience(
        self, app, db_session: Session, event: EventPost
    ) -> None:
        event.content = "Le secret de la conférence"
        event.audience = [CommunityEnum.PRESS_MEDIA.value]
        db_session.flush()
        journalist = _member(db_session, "insider", RoleEnum.PRESS_MEDIA)

        with app.test_request_context("/"):
            g.user = journalist
            html = render_template(
                "pages/event--main.j2",
                event=EventDetailVM(event),
                sees_content=sees_full_content(journalist, event),
                sees_access_details=sees_access_details(journalist, event),
                audience=event.audience,
            )

        assert "Le secret de la conférence" in html
