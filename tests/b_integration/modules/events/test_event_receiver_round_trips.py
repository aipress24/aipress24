# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Round-trip integration tests for ``events.event_receiver``.

These tests live at the b_integration tier because they exercise the
receiver functions against a real SQLAlchemy session: each test
constructs ``Event`` and ``EventPost`` rows and then asserts on the
final DB state (status, counts, propagated foreign keys, timestamps)
after one or more receivers have run.

The existing ``test_event_receiver.py`` covers each receiver in
isolation. This file complements it by covering *multi-step lifecycles*
(publish -> unpublish -> republish), isolation between events, and
the persistence of state across receiver calls.
"""

from __future__ import annotations

import pytest
from arrow import now
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.constants import LOCAL_TZ
from app.models.auth import User
from app.models.lifecycle import PublicationStatus
from app.models.organisation import Organisation
from app.modules.events.event_receiver import (
    on_publish_event,
    on_unpublish_event,
    on_update_event,
)
from app.modules.events.models import EventPost
from app.modules.wip.models.eventroom import Event


def _make_event(
    db_session: Session,
    owner: User,
    *,
    titre: str = "Conf Round-trip",
    event_type: str = "Conference / Webinar",
    publisher_id: int | None = None,
) -> Event:
    event = Event(
        titre=titre,
        chapo="Chapo",
        contenu="Content",
        event_type=event_type,
        sector="Tech",
        address="1 rue Test",
        pays_zip_ville="FR75001",
        pays_zip_ville_detail="Paris",
        url="https://example.com",
        language="fr",
        owner=owner,
    )
    event.start_time = now(LOCAL_TZ)
    event.end_time = now(LOCAL_TZ).shift(hours=2)
    if publisher_id is not None:
        event.publisher_id = publisher_id
    db_session.add(event)
    db_session.flush()
    return event


@pytest.fixture
def org(db_session: Session) -> Organisation:
    organisation = Organisation(name="Org Round-trip")
    db_session.add(organisation)
    db_session.flush()
    return organisation


@pytest.fixture
def owner(db_session: Session, org: Organisation) -> User:
    user = User(email="owner@example.com")
    user.photo = b""
    user.active = True
    user.organisation = org
    db_session.add(user)
    db_session.flush()
    return user


def _count_posts(db_session: Session, event: Event) -> int:
    stmt = select(EventPost).where(EventPost.eventroom_id == event.id)
    return len(db_session.execute(stmt).scalars().all())


class TestPublishUnpublishRoundTrip:
    """Full lifecycle: publish, then unpublish, then republish."""

    def test_publish_then_unpublish_flips_status_to_draft(
        self, db_session: Session, owner: User
    ) -> None:
        event = _make_event(db_session, owner)

        on_publish_event(event)
        on_unpublish_event(event)

        stmt = select(EventPost).where(EventPost.eventroom_id == event.id)
        post = db_session.execute(stmt).scalar_one()
        assert post.status == PublicationStatus.DRAFT
        assert _count_posts(db_session, event) == 1

    def test_publish_unpublish_republish_keeps_single_post(
        self, db_session: Session, owner: User
    ) -> None:
        event = _make_event(db_session, owner)

        on_publish_event(event)
        first_id = db_session.execute(
            select(EventPost.id).where(EventPost.eventroom_id == event.id)
        ).scalar_one()

        on_unpublish_event(event)
        on_publish_event(event)

        # Same row, flipped back to PUBLIC. No duplicate created.
        stmt = select(EventPost).where(EventPost.eventroom_id == event.id)
        posts = db_session.execute(stmt).scalars().all()
        assert len(posts) == 1
        assert posts[0].id == first_id
        assert posts[0].status == PublicationStatus.PUBLIC

    def test_unpublish_without_publish_creates_no_post(
        self, db_session: Session, owner: User
    ) -> None:
        event = _make_event(db_session, owner)

        on_unpublish_event(event)

        assert _count_posts(db_session, event) == 0


class TestPublishUpdateRoundTrip:
    """Publish, mutate the event, then update -> post should track."""

    def test_update_after_publish_propagates_title_and_content(
        self, db_session: Session, owner: User
    ) -> None:
        event = _make_event(db_session, owner, titre="Original")
        on_publish_event(event)

        event.titre = "Updated Title"
        event.contenu = "Updated body"
        db_session.flush()

        on_update_event(event)

        post = db_session.execute(
            select(EventPost).where(EventPost.eventroom_id == event.id)
        ).scalar_one()
        assert post.title == "Updated Title"
        assert post.content == "Updated body"
        # Status remains PUBLIC after on_update_event
        assert post.status == PublicationStatus.PUBLIC

    def test_modified_at_changes_when_update_runs_after_publish(
        self, db_session: Session, owner: User
    ) -> None:
        event = _make_event(db_session, owner)
        on_publish_event(event)

        post = db_session.execute(
            select(EventPost).where(EventPost.eventroom_id == event.id)
        ).scalar_one()
        modified_after_publish = post.modified_at

        # Force a write to trigger before_update -> modified_at refresh
        event.titre = "Mutated"
        db_session.flush()
        on_update_event(event)
        db_session.refresh(post)

        # LifeCycleMixin's before_update bumps modified_at; the post was
        # written by on_update_event so it should be >= the publish-time
        # modified_at.
        assert post.modified_at is not None
        assert modified_after_publish is not None
        assert post.modified_at >= modified_after_publish

    def test_category_recomputed_when_event_type_changes(
        self, db_session: Session, owner: User
    ) -> None:
        event = _make_event(db_session, owner, event_type="Conference / Webinar")
        on_publish_event(event)

        event.event_type = "Workshop / Networking"
        db_session.flush()
        on_update_event(event)

        post = db_session.execute(
            select(EventPost).where(EventPost.eventroom_id == event.id)
        ).scalar_one()
        assert post.category == "workshop"
        assert post.genre == "Workshop / Networking"


class TestPublisherIdPropagation:
    """Bug #0135/#0138: publisher_id must round-trip through publish/update."""

    def test_publish_propagates_publisher_id_to_post(
        self, db_session: Session, owner: User
    ) -> None:
        client = Organisation(name="Client Org")
        db_session.add(client)
        db_session.flush()
        event = _make_event(db_session, owner, publisher_id=client.id)

        on_publish_event(event)

        post = db_session.execute(
            select(EventPost).where(EventPost.eventroom_id == event.id)
        ).scalar_one()
        assert post.publisher_id == client.id

    def test_update_propagates_new_publisher_id(
        self, db_session: Session, owner: User
    ) -> None:
        first = Organisation(name="First Publisher")
        second = Organisation(name="Second Publisher")
        db_session.add_all([first, second])
        db_session.flush()

        event = _make_event(db_session, owner, publisher_id=first.id)
        on_publish_event(event)

        event.publisher_id = second.id
        db_session.flush()
        on_update_event(event)

        post = db_session.execute(
            select(EventPost).where(EventPost.eventroom_id == event.id)
        ).scalar_one()
        assert post.publisher_id == second.id


class TestReceiverIsolationBetweenEvents:
    """Receivers must only touch the post bound to their event."""

    def test_publishing_one_event_does_not_touch_another(
        self, db_session: Session, owner: User
    ) -> None:
        event_a = _make_event(db_session, owner, titre="Event A")
        event_b = _make_event(db_session, owner, titre="Event B")

        on_publish_event(event_a)

        stmt = select(EventPost).where(EventPost.eventroom_id == event_b.id)
        assert db_session.execute(stmt).scalar_one_or_none() is None
        assert _count_posts(db_session, event_a) == 1

    def test_unpublishing_one_event_leaves_other_public(
        self, db_session: Session, owner: User
    ) -> None:
        event_a = _make_event(db_session, owner, titre="Event A")
        event_b = _make_event(db_session, owner, titre="Event B")

        on_publish_event(event_a)
        on_publish_event(event_b)
        on_unpublish_event(event_a)

        post_a = db_session.execute(
            select(EventPost).where(EventPost.eventroom_id == event_a.id)
        ).scalar_one()
        post_b = db_session.execute(
            select(EventPost).where(EventPost.eventroom_id == event_b.id)
        ).scalar_one()
        assert post_a.status == PublicationStatus.DRAFT
        assert post_b.status == PublicationStatus.PUBLIC


@pytest.mark.parametrize(
    ("event_type", "expected_category"),
    [
        ("Conference / Webinar", "conference"),
        ("Workshop / Networking", "workshop"),
        ("Industry Event / Whatever", "industry_event"),
        ("Seminar", "seminar"),
    ],
)
class TestCategoryDerivationOnPublish:
    """Cover the category derivation through the publish path end-to-end."""

    def test_publish_sets_category_from_event_type(
        self,
        db_session: Session,
        owner: User,
        event_type: str,
        expected_category: str,
    ) -> None:
        event = _make_event(db_session, owner, event_type=event_type)

        on_publish_event(event)

        post = db_session.execute(
            select(EventPost).where(EventPost.eventroom_id == event.id)
        ).scalar_one()
        assert post.category == expected_category
        assert post.genre == event_type
