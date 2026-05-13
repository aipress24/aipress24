# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Integration coverage for `SanitizedHTML` applied to real models.

We exercise the column type through a write/read cycle on each model
that carries it. The contract is:

  1. After commit, the DB value contains no `<script>`, `<style>`,
     `<iframe>`, event handlers, or `javascript:` URLs — regardless of
     what the application code passed in.
  2. Legitimate whitelisted markup (formatting, links, images) is
     preserved.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from app.models.admin import Promotion
from app.models.auth import User
from app.modules.swork.models import Group
from app.modules.wip.models.comroom import Communique
from app.modules.wip.models.eventroom import Event
from app.modules.wire.models import ArticlePost

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


_ATTACK_PAYLOAD = (
    "<p>ok</p>"
    "<script>alert(1)</script>"
    '<a href="javascript:alert(1)">x</a>'
    '<img src="https://ok/x.png" onerror="alert(1)">'
    "<iframe src='https://evil'></iframe>"
    '<a href="https://example.com" onclick="alert(1)">good</a>'
)


def _make_user(db_session: Session) -> User:
    # Unique email per call so test classes can share the integration
    # DB without UNIQUE-constraint stepping on each other.
    user = User(email=f"sanitize-{uuid.uuid4().hex[:8]}@example.com", active=True)
    db_session.add(user)
    db_session.flush()
    return user


def _assert_sanitized(value: str) -> None:
    """Every contract bullet, against one stored value."""
    assert "<script" not in value
    assert "</script>" not in value
    assert "javascript:" not in value
    assert "onerror" not in value
    assert "onclick" not in value
    assert "<iframe" not in value
    # Legitimate markup retained.
    assert "<p>ok</p>" in value
    assert 'href="https://example.com"' in value
    assert 'src="https://ok/x.png"' in value


class TestEventContentSanitizeOnWrite:
    def test_event_contenu_sanitized(self, db_session: Session):
        user = _make_user(db_session)
        event = Event(titre="t", contenu=_ATTACK_PAYLOAD, owner_id=user.id)
        db_session.add(event)
        db_session.flush()

        db_session.expire_all()
        reloaded = db_session.get(Event, event.id)
        assert reloaded is not None
        _assert_sanitized(reloaded.contenu)


class TestCommuniqueContentSanitizeOnWrite:
    def test_communique_contenu_sanitized(self, db_session: Session):
        user = _make_user(db_session)
        com = Communique(titre="t", contenu=_ATTACK_PAYLOAD, owner_id=user.id)
        db_session.add(com)
        db_session.flush()

        db_session.expire_all()
        reloaded = db_session.get(Communique, com.id)
        assert reloaded is not None
        _assert_sanitized(reloaded.contenu)


class TestGroupDescriptionSanitizeOnWrite:
    def test_group_description_sanitized(self, db_session: Session):
        user = _make_user(db_session)
        group = Group(
            name="g",
            description=_ATTACK_PAYLOAD,
            owner_id=user.id,
            privacy="public",
        )
        db_session.add(group)
        db_session.flush()

        db_session.expire_all()
        reloaded = db_session.get(Group, group.id)
        assert reloaded is not None
        _assert_sanitized(reloaded.description)


class TestPromotionBodySanitizeOnWrite:
    def test_promotion_body_sanitized(self, db_session: Session):
        slug = f"promo-{uuid.uuid4().hex[:8]}"
        promo = Promotion(slug=slug, title="t", body=_ATTACK_PAYLOAD)
        db_session.add(promo)
        db_session.flush()

        db_session.expire_all()
        reloaded = db_session.get(Promotion, slug)
        assert reloaded is not None
        _assert_sanitized(reloaded.body)


class TestBaseContentSanitizeOnWrite:
    """ArticlePost / PressReleasePost / EventPost / ShortPost / Comment
    all inherit `content` from BaseContent, which now carries the
    SanitizedHTML type. Verify via ArticlePost (the easiest concrete
    subclass to construct here).
    """

    def test_article_post_content_sanitized(self, db_session: Session):
        user = _make_user(db_session)
        post = ArticlePost(title="t", content=_ATTACK_PAYLOAD, owner_id=user.id)
        db_session.add(post)
        db_session.flush()

        db_session.expire_all()
        reloaded = db_session.get(ArticlePost, post.id)
        assert reloaded is not None
        _assert_sanitized(reloaded.content)
