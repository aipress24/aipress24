# Copyright (c) 2025, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only
"""The domain repositories are the single source of "publicly visible".

These exercise the visibility-gated repository reads directly (flush-only,
no commit), covering wire / events / marketplace / organisations / members —
including biz, which the public API does not expose.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import arrow
from sqlalchemy.orm import Session

from app.models.auth import User
from app.models.lifecycle import PublicationStatus
from app.models.organisation import Organisation
from app.models.repositories import OrganisationRepository, UserRepository
from app.modules.biz.models._offers import MissionOffer
from app.modules.biz.repositories import MissionOfferRepository
from app.modules.events.models import EventPost
from app.modules.events.repositories import EventPostRepository
from app.modules.wire.models import ArticlePost
from app.modules.wire.repositories import ArticlePostRepository


def _user(db_session: Session) -> User:
    user = User(email=f"vis-{uuid.uuid4().hex[:8]}@example.com", active=True)
    db_session.add(user)
    db_session.flush()
    return user


def test_wire_repo_lists_only_publicly_visible(db_session: Session) -> None:
    user = _user(db_session)
    now = datetime.now(UTC)
    db_session.add_all(
        [
            ArticlePost(
                owner=user,
                title="ok",
                status=PublicationStatus.PUBLIC,
                published_at=now,
            ),
            ArticlePost(
                owner=user,
                title="draft",
                status=PublicationStatus.DRAFT,
                published_at=now,
            ),
            ArticlePost(owner=user, title="no-pub", status=PublicationStatus.PUBLIC),
            ArticlePost(
                owner=user,
                title="expired",
                status=PublicationStatus.PUBLIC,
                published_at=now,
                expires_at=now - timedelta(days=1),
            ),
        ]
    )
    db_session.flush()

    rows, total = ArticlePostRepository(session=db_session).list_published(
        limit=50, offset=0
    )
    assert total == 1
    assert {r.title for r in rows} == {"ok"}


def test_events_repo_lists_only_published(db_session: Session) -> None:
    user = _user(db_session)
    db_session.add_all(
        [
            EventPost(
                owner=user,
                title="pub",
                content="c",
                summary="s",
                status=PublicationStatus.PUBLIC,
                published_at=arrow.utcnow(),
            ),
            EventPost(
                owner=user,
                title="draft",
                content="c",
                summary="s",
                status=PublicationStatus.DRAFT,
            ),
        ]
    )
    db_session.flush()

    rows, total = EventPostRepository(session=db_session).list_published(
        limit=50, offset=0
    )
    assert total == 1
    assert rows[0].title == "pub"


def test_biz_repo_lists_only_published(db_session: Session) -> None:
    user = _user(db_session)
    db_session.add_all(
        [
            MissionOffer(
                owner=user,
                title="pub",
                status=PublicationStatus.PUBLIC,
                published_at=arrow.utcnow(),
            ),
            MissionOffer(owner=user, title="draft", status=PublicationStatus.DRAFT),
        ]
    )
    db_session.flush()

    rows, total = MissionOfferRepository(session=db_session).list_published(
        limit=50, offset=0
    )
    assert total == 1
    assert rows[0].title == "pub"


def test_organisation_repo_excludes_soft_deleted(db_session: Session) -> None:
    live = Organisation(name=f"Live {uuid.uuid4().hex[:6]}")
    gone = Organisation(name=f"Gone {uuid.uuid4().hex[:6]}")
    gone.deleted_at = arrow.utcnow()
    db_session.add_all([live, gone])
    db_session.flush()

    rows, _ = OrganisationRepository(session=db_session).list_public(
        limit=100, offset=0
    )
    names = {o.name for o in rows}
    assert live.name in names
    assert gone.name not in names


def test_user_repo_excludes_clone_inactive_deleted(db_session: Session) -> None:
    listable = _user(db_session)
    inactive = User(email=f"i-{uuid.uuid4().hex[:8]}@example.com", active=False)
    clone = User(
        email=f"c-{uuid.uuid4().hex[:8]}@example.com", active=True, is_clone=True
    )
    deleted = User(email=f"d-{uuid.uuid4().hex[:8]}@example.com", active=True)
    deleted.deleted_at = arrow.utcnow()
    db_session.add_all([inactive, clone, deleted])
    db_session.flush()

    rows, _ = UserRepository(session=db_session).list_public_members(
        limit=200, offset=0
    )
    ids = {u.id for u in rows}
    assert listable.id in ids
    assert inactive.id not in ids
    assert clone.id not in ids
    assert deleted.id not in ids
