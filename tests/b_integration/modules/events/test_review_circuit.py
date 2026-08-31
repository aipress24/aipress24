# Copyright (c) 2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Qui relit quoi — `REL-02`, `REL-03`, `REL-07`.

La spécification nomme « BW Master » et « BW Deputy Master ». **Ces
rôles n'existent pas** dans le dépôt, qui connaît `BW_OWNER`, `BWMi`,
`BWPRi`, `BWMe`, `BWPRe`, et dont la notion d'habilitation est une
*mission* accordée sur le Business Wall. Le relecteur est donc « qui
peut décider des événements de cette organisation », ce que la règle
décrit en d'autres mots.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import arrow
import pytest
from svcs.flask import container

from app.constants import LOCAL_TZ
from app.models.auth import User
from app.models.lifecycle import PublicationStatus
from app.models.organisation import Organisation
from app.modules.bw.bw_activation.models.business_wall import BusinessWall, BWStatus
from app.modules.bw.bw_activation.models.role import (
    BWRoleType,
    InvitationStatus,
    PermissionType,
    RoleAssignment,
    RolePermission,
)
from app.modules.bw.bw_activation.user_utils import (
    get_active_business_wall_for_organisation,
)
from app.modules.events.notifications import (
    notify_sent_back,
    notify_submitted_for_review,
)
from app.modules.events.review import (
    events_to_review,
    is_reviewer,
    review_required,
    reviewers_of,
)
from app.modules.wip.models.eventroom import Event
from app.services.notifications import NotificationService

if TYPE_CHECKING:
    from flask import Flask
    from sqlalchemy.orm import Session


def _user(db_session: Session, tag: str) -> User:
    user = User(email=f"rev-{tag}@example.com", first_name=tag.title())
    user.photo = b""
    user.active = True
    db_session.add(user)
    db_session.flush()
    return user


@pytest.fixture
def owner(db_session: Session) -> User:
    return _user(db_session, "bw-owner")


@pytest.fixture
def org(db_session: Session, owner: User) -> Organisation:
    """Une organisation dotée d'un Business Wall actif."""
    organisation = Organisation(name="Média relecteur")
    db_session.add(organisation)
    db_session.flush()

    bw = BusinessWall(
        organisation_id=organisation.id,
        bw_type="media",
        status=BWStatus.ACTIVE.value,
        owner_id=owner.id,
        payer_id=owner.id,
    )
    db_session.add(bw)
    db_session.flush()
    organisation.bw_id = bw.id
    db_session.flush()
    return organisation


def _grant_events(db_session: Session, org: Organisation, user: User) -> None:
    """Accorder la mission « événements » à un membre, sur le BW de
    l'organisation."""
    bw = get_active_business_wall_for_organisation(org)
    assignment = RoleAssignment(
        business_wall_id=bw.id,
        user_id=user.id,
        role_type=BWRoleType.BWMI.value,
        invitation_status=InvitationStatus.ACCEPTED.value,
    )
    db_session.add(assignment)
    db_session.flush()
    db_session.add(
        RolePermission(
            role_assignment_id=assignment.id,
            permission_type=PermissionType.EVENTS.value,
            is_granted=True,
        )
    )
    db_session.flush()


@pytest.fixture
def author(db_session: Session, org: Organisation) -> User:
    user = _user(db_session, "author")
    user.organisation = org
    db_session.flush()
    return user


def _draft(db_session: Session, author: User, org: Organisation) -> Event:
    event = Event(
        titre="Salon à relire",
        chapo="Chapo",
        contenu="<p>Programme</p>",
        owner=author,
        publisher=org,
    )
    event.status = PublicationStatus.DRAFT
    event.address = "1 rue de la Paix, Paris"
    event.start_time = arrow.now(LOCAL_TZ).shift(days=5)
    event.end_time = arrow.now(LOCAL_TZ).shift(days=6)
    db_session.add(event)
    db_session.flush()
    return event


def _messages(user: User) -> list[str]:
    return [
        n.message for n in container.get(NotificationService).get_notifications(user)
    ]


class TestWhoIsAReviewer:
    def test_the_business_wall_owner_is_one_of_right(
        self, db_session: Session, org: Organisation, owner: User
    ) -> None:
        """Il porte toutes les missions."""
        assert is_reviewer(owner, org)

    def test_and_so_is_a_granted_mission(
        self, db_session: Session, org: Organisation
    ) -> None:
        member = _user(db_session, "granted")
        _grant_events(db_session, org, member)

        assert is_reviewer(member, org)

    def test_but_not_a_plain_member_of_the_organisation(
        self, db_session: Session, org: Organisation, author: User
    ) -> None:
        """C'est la leçon du lot L4 : dans un média de deux cents
        journalistes, l'appartenance ouvrirait la relecture à tout le
        monde."""
        assert author.organisation_id == org.id
        assert not is_reviewer(author, org)

    def test_nor_a_stranger(self, db_session: Session, org: Organisation) -> None:
        assert not is_reviewer(_user(db_session, "stranger"), org)

    def test_an_organisation_without_a_business_wall_has_no_reviewers(
        self, db_session: Session
    ) -> None:
        bare = Organisation(name="Sans BW")
        db_session.add(bare)
        db_session.flush()

        assert reviewers_of(bare) == []

    def test_and_neither_does_no_organisation_at_all(self) -> None:
        assert reviewers_of(None) == []


class TestTheFlagIsOptional:
    """REL-03 — à `False`, le parcours actuel est intégralement
    préservé."""

    def test_organisations_do_not_review_by_default(
        self, db_session: Session, org: Organisation
    ) -> None:
        assert org.event_review_required is False
        assert not review_required(org)

    def test_turning_it_on_is_all_it_takes(
        self, db_session: Session, org: Organisation
    ) -> None:
        org.event_review_required = True
        db_session.flush()

        assert review_required(org)

    def test_an_event_without_a_publisher_never_reviews(self) -> None:
        """Sans organisation éditrice, personne ne relit — et le bloquer
        en relecture l'y laisserait pour toujours."""
        assert not review_required(None)

    def test_nor_does_an_organisation_with_nobody_to_review(
        self, db_session: Session
    ) -> None:
        """Le drapeau posé, puis l'abonnement qui expire : la mission
        « événements » se lit sur le Business Wall, et sans lui la liste
        des relecteurs est vide. Exiger une relecture que personne ne
        peut faire n'est pas une exigence, c'est un blocage — l'auteur
        n'a plus la main, et nul ne peut la prendre.
        """
        orphan = Organisation(name="BW expiré")
        orphan.event_review_required = True
        db_session.add(orphan)
        db_session.flush()

        assert orphan.event_review_required is True
        assert reviewers_of(orphan) == []
        assert not review_required(orphan)


class TestTheNotifications:
    """REL-07."""

    def test_submitting_reaches_every_reviewer(
        self, app: Flask, db_session: Session, org: Organisation, author: User, owner
    ) -> None:
        second = _user(db_session, "second-reviewer")
        _grant_events(db_session, org, second)
        event = _draft(db_session, author, org)

        with app.test_request_context("/"):
            event.submit_for_review()
            count = notify_submitted_for_review(event, reviewers_of(org))
            db_session.flush()

        assert count == 2
        for reviewer in (owner, second):
            assert any(event.title in m for m in _messages(reviewer))

    def test_and_not_the_author(
        self, app: Flask, db_session: Session, org: Organisation, author: User
    ) -> None:
        event = _draft(db_session, author, org)

        with app.test_request_context("/"):
            event.submit_for_review()
            notify_submitted_for_review(event, reviewers_of(org))
            db_session.flush()

        assert _messages(author) == []

    def test_sending_back_carries_the_reason(
        self, app: Flask, db_session: Session, org: Organisation, author: User
    ) -> None:
        """Le motif est le contenu utile du message : sans lui, l'auteur
        sait que son événement est revenu mais pas ce qu'il doit
        corriger."""
        event = _draft(db_session, author, org)
        event.submit_for_review()

        with app.test_request_context("/"):
            event.send_back("Il manque le nom de la salle.")
            notify_sent_back(event, "Il manque le nom de la salle.")
            db_session.flush()

        assert any("Il manque le nom de la salle." in m for m in _messages(author)), (
            _messages(author)
        )


class TestTheReviewQueue:
    """REL-06 — l'écran « À relire », et son compteur.

    La liste ordinaire de l'atelier est filtrée par propriétaire : sans
    cette requête, un relecteur ne verrait jamais l'événement d'un
    collègue, et c'est précisément ce qu'il doit voir.
    """

    def test_a_reviewer_sees_a_colleagues_submission(
        self, app: Flask, db_session: Session, org: Organisation, author: User, owner
    ) -> None:
        owner.organisation = org
        event = _draft(db_session, author, org)
        event.submit_for_review()
        db_session.flush()

        with app.test_request_context("/"):
            queue = events_to_review(owner)

        assert [e.id for e in queue] == [event.id]

    def test_the_author_does_not_see_their_own_queue(
        self, app: Flask, db_session: Session, org: Organisation, author: User
    ) -> None:
        """Soumettre, c'est passer la main."""
        event = _draft(db_session, author, org)
        event.submit_for_review()
        db_session.flush()

        with app.test_request_context("/"):
            assert events_to_review(author) == []

    def test_a_draft_is_not_in_the_queue(
        self, app: Flask, db_session: Session, org: Organisation, author: User, owner
    ) -> None:
        owner.organisation = org
        _draft(db_session, author, org)
        db_session.flush()

        with app.test_request_context("/"):
            assert events_to_review(owner) == []

    def test_nor_is_another_organisations_event(
        self, app: Flask, db_session: Session, org: Organisation, owner: User
    ) -> None:
        owner.organisation = org
        other_org = Organisation(name="Autre média")
        db_session.add(other_org)
        db_session.flush()
        stranger = _user(db_session, "other-author")
        event = _draft(db_session, stranger, other_org)
        event.submit_for_review()
        db_session.flush()

        with app.test_request_context("/"):
            assert events_to_review(owner) == []

    def test_a_deleted_event_leaves_the_queue(
        self, app: Flask, db_session: Session, org: Organisation, author: User, owner
    ) -> None:
        owner.organisation = org
        event = _draft(db_session, author, org)
        event.submit_for_review()
        event.deleted_at = arrow.utcnow()
        db_session.flush()

        with app.test_request_context("/"):
            assert events_to_review(owner) == []
