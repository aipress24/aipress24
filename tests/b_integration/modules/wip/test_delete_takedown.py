# Copyright (c) 2025, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only
"""Deleting a published newsroom source must take its public mirror down.

Publishing an Article / Communique / Event creates a public "mirror"
(ArticlePost / PressReleasePost / EventPost). Soft-deleting the source used
to leave that mirror at status=PUBLIC, so it kept being served by the public
API, the News portal and the search index. The CBV `_post_delete_model`
hook now re-emits the unpublish signal, flipping the mirror to DRAFT (which
`published_filters` excludes). These tests assert that end state.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import arrow
from sqlalchemy import select

from app.models.auth import User
from app.models.lifecycle import PublicationStatus
from app.models.organisation import Organisation
from app.modules.events.models import EventPost
from app.modules.events.repositories import EventPostRepository
from app.modules.wip.crud.cbvs.articles import ArticlesWipView
from app.modules.wip.crud.cbvs.communiques import CommuniquesWipView
from app.modules.wip.crud.cbvs.events import EventsWipView
from app.modules.wip.models import Article, Communique
from app.modules.wip.models.eventroom import Event
from app.modules.wire.models import ArticlePost, PressReleasePost
from app.modules.wire.repositories import (
    ArticlePostRepository,
    PressReleasePostRepository,
)
from app.signals import article_published, communique_published, event_published

if TYPE_CHECKING:
    from flask import Flask
    from flask_sqlalchemy import SQLAlchemy


def _published_ids(repo) -> set[int]:
    rows, _ = repo.list_published(limit=100, offset=0)
    return {row.id for row in rows}


def test_deleting_published_article_takes_the_mirror_down(
    app: Flask, db: SQLAlchemy
) -> None:
    with app.app_context():
        user = User(email="del-article@example.com")
        media = Organisation(name="Media A")
        db.session.add_all([user, media])
        db.session.flush()
        article = Article(
            owner=user,
            titre="Takedown article",
            chapo="c",
            contenu="body",
            date_parution_prevue=arrow.now().datetime,
            media_id=media.id,
            commanditaire_id=user.id,
        )
        db.session.add(article)
        db.session.flush()

        article_published.send(article)
        mirror = db.session.scalar(
            select(ArticlePost).where(ArticlePost.newsroom_id == article.id)
        )
        assert mirror is not None
        assert mirror.status == PublicationStatus.PUBLIC
        mirror.published_at = arrow.utcnow().datetime
        db.session.flush()

        repo = ArticlePostRepository(session=db.session)
        assert mirror.id in _published_ids(repo)  # served before deletion

        ArticlesWipView()._post_delete_model(article)

        assert mirror.status == PublicationStatus.DRAFT
        assert mirror.id not in _published_ids(repo)  # gone after deletion


def test_deleting_published_communique_takes_the_mirror_down(
    app: Flask, db: SQLAlchemy
) -> None:
    with app.app_context():
        user = User(email="del-communique@example.com")
        publisher = Organisation(name="Publisher A")
        db.session.add_all([user, publisher])
        db.session.flush()
        communique = Communique(
            owner=user,
            titre="Takedown communique",
            chapo="c",
            contenu="body",
            publisher_id=publisher.id,
        )
        db.session.add(communique)
        db.session.flush()

        communique_published.send(communique)
        mirror = db.session.scalar(
            select(PressReleasePost).where(
                PressReleasePost.newsroom_id == communique.id
            )
        )
        assert mirror is not None
        assert mirror.status == PublicationStatus.PUBLIC
        mirror.published_at = arrow.utcnow().datetime
        db.session.flush()

        repo = PressReleasePostRepository(session=db.session)
        assert mirror.id in _published_ids(repo)

        CommuniquesWipView()._post_delete_model(communique)

        assert mirror.status == PublicationStatus.DRAFT
        assert mirror.id not in _published_ids(repo)


def test_deleting_published_event_takes_the_mirror_down(
    app: Flask, db: SQLAlchemy
) -> None:
    with app.app_context():
        user = User(email="del-event@example.com")
        publisher = Organisation(name="Publisher B")
        db.session.add_all([user, publisher])
        db.session.flush()
        event = Event(
            owner=user,
            titre="Takedown event",
            chapo="c",
            contenu="body",
            publisher_id=publisher.id,
        )
        db.session.add(event)
        db.session.flush()

        event_published.send(event)
        mirror = db.session.scalar(
            select(EventPost).where(EventPost.eventroom_id == event.id)
        )
        assert mirror is not None
        assert mirror.status == PublicationStatus.PUBLIC
        mirror.published_at = arrow.utcnow()
        db.session.flush()

        repo = EventPostRepository(session=db.session)
        assert mirror.id in _published_ids(repo)

        EventsWipView()._post_delete_model(event)

        assert mirror.status == PublicationStatus.DRAFT
        assert mirror.id not in _published_ids(repo)
