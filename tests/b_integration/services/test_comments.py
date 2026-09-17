# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from typing import TYPE_CHECKING

import arrow

from app.flask.routing import url_for
from app.models.auth import User
from app.models.comment import Comment
from app.modules.events.models import EventPost
from app.modules.wire.models import ArticlePost, Post, PressReleasePost
from app.services.comments import (
    delete_comment,
    resolve_comment_parent,
    sync_comment_count_for_parent,
    sync_parent_comment_count,
)

if TYPE_CHECKING:
    from flask_sqlalchemy import SQLAlchemy


def test_resolve_comment_parent_success(db: SQLAlchemy) -> None:
    user = User(email="test_parent@example.com")
    db.session.add(user)
    db.session.flush()

    article = ArticlePost(title="Test Article", owner=user)
    press = PressReleasePost(title="Test PR", owner=user)
    post = Post(title="Test Wire Post", owner=user)
    event = EventPost(title="Test Event", owner=user)
    db.session.add_all([article, press, post, event])
    db.session.flush()

    c_art = Comment(object_id=f"article:{article.id}", owner=user)
    c_pr = Comment(object_id=f"press-release:{press.id}", owner=user)
    c_post = Comment(object_id=f"post:{post.id}", owner=user)
    c_event = Comment(object_id=f"event:{event.id}", owner=user)

    assert resolve_comment_parent(c_art) == article
    assert resolve_comment_parent(c_pr) == press
    assert resolve_comment_parent(c_post) == post
    assert resolve_comment_parent(c_event) == event


def test_sync_and_delete_comment_on_post(db: SQLAlchemy) -> None:
    user = User(email="test_sync@example.com")
    db.session.add(user)
    db.session.flush()

    post = ArticlePost(title="Article for Comments", owner=user, comment_count=0)
    db.session.add(post)
    db.session.flush()

    c1 = Comment(object_id=f"article:{post.id}", content="Comment 1", owner=user)
    c2 = Comment(object_id=f"article:{post.id}", content="Comment 2", owner=user)
    c3 = Comment(object_id=f"article:{post.id}", content="Comment 3", owner=user)
    db.session.add_all([c1, c2, c3])
    db.session.flush()

    # Initial sync
    count = sync_comment_count_for_parent(post)
    assert count == 3
    assert post.comment_count == 3

    # Delete one comment
    delete_comment(c1)
    assert c1.deleted_at is not None
    assert post.comment_count == 2

    # Delete second comment
    delete_comment(c2)
    assert c2.deleted_at is not None
    assert post.comment_count == 1

    # Delete third comment
    delete_comment(c3)
    assert c3.deleted_at is not None
    assert post.comment_count == 0


def test_sync_and_delete_comment_on_event(db: SQLAlchemy) -> None:
    user = User(email="test_event_sync@example.com")
    db.session.add(user)
    db.session.flush()

    event = EventPost(title="Event for Comments", owner=user, comment_count=0)
    db.session.add(event)
    db.session.flush()

    c1 = Comment(object_id=f"event:{event.id}", content="Event Comment 1", owner=user)
    c2 = Comment(object_id=f"event:{event.id}", content="Event Comment 2", owner=user)
    db.session.add_all([c1, c2])
    db.session.flush()

    sync_comment_count_for_parent(event)
    assert event.comment_count == 2

    delete_comment(c1)
    assert c1.deleted_at is not None
    assert event.comment_count == 1

    delete_comment(c2)
    assert c2.deleted_at is not None
    assert event.comment_count == 0


def test_delete_comment_custom_timestamp(db: SQLAlchemy) -> None:
    user = User(email="test_custom_ts@example.com")
    db.session.add(user)
    db.session.flush()

    post = Post(title="Post Ts", owner=user, comment_count=1)
    c = Comment(object_id=f"post:{post.id}", content="Ts comment", owner=user)
    db.session.add_all([post, c])
    db.session.flush()

    custom_time = arrow.get("2026-09-01T12:00:00+02:00")
    delete_comment(c, deleted_at=custom_time)

    assert c.deleted_at == custom_time
    assert post.comment_count == 0


def test_delete_comment_orphan(db: SQLAlchemy) -> None:
    user = User(email="test_orphan@example.com")
    db.session.add(user)
    db.session.flush()

    c = Comment(content="No parent", object_id=None, owner=user)
    db.session.add(c)
    db.session.flush()

    delete_comment(c)
    assert c.deleted_at is not None
    assert sync_parent_comment_count(c) is None


def test_url_for_comment(db: SQLAlchemy) -> None:
    user = User(email="test_routing@example.com")
    db.session.add(user)
    db.session.flush()

    post = ArticlePost(title="Article URL", owner=user)
    event = EventPost(title="Event URL", owner=user)
    db.session.add_all([post, event])
    db.session.flush()

    c_post = Comment(object_id=f"article:{post.id}", owner=user)
    c_event = Comment(object_id=f"event:{event.id}", owner=user)
    c_none = Comment(object_id=None, owner=user)
    db.session.add_all([c_post, c_event, c_none])
    db.session.flush()

    url_post = url_for(c_post)
    assert f"#comment-{c_post.id}" in url_post

    url_event = url_for(c_event)
    assert f"#comment-{c_event.id}" in url_event

    assert url_for(c_none) == "#NONE"


def test_sync_parent_comment_count_already_deleted(db: SQLAlchemy) -> None:
    user = User(email="test_del_sync@example.com")
    db.session.add(user)
    db.session.flush()

    post = Post(title="Post Deleted Sync", owner=user, comment_count=1)
    c = Comment(object_id=f"post:{post.id}", content="Already deleted", owner=user)
    db.session.add_all([post, c])
    db.session.flush()

    c.deleted_at = arrow.now()
    count = sync_parent_comment_count(c)
    assert count == 0
    assert post.comment_count == 0
