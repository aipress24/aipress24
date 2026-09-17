# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from app.models.comment import Comment
from app.modules.events.models import EventPost
from app.modules.wire.models import ArticlePost, Post, PressReleasePost
from app.services.comments import (
    get_comment_object_id,
    resolve_comment_parent,
)


def test_get_comment_object_id() -> None:
    article_post = ArticlePost(id=10)
    press_post = PressReleasePost(id=20)
    event_post = EventPost(id=30)
    generic_post = Post(id=40)

    assert get_comment_object_id(article_post) == "article:10"
    assert get_comment_object_id(press_post) == "press-release:20"
    assert get_comment_object_id(event_post) == "event:30"
    assert get_comment_object_id(generic_post) == "post:40"


def test_resolve_comment_parent_edge_cases() -> None:
    c1 = Comment()
    assert resolve_comment_parent(c1) is None

    c2 = Comment(object_id="")
    assert resolve_comment_parent(c2) is None

    c3 = Comment(object_id="article:not_a_number")
    assert resolve_comment_parent(c3) is None

    c4 = Comment(object_id="unknown_prefix:123")
    assert resolve_comment_parent(c4) is None

    c5 = Comment(object_id="post:999999")
    assert resolve_comment_parent(c5) is None
