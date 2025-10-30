# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from flask_sqlalchemy import SQLAlchemy

from app.models.auth import User
from app.modules.wire.models import ArticlePost
from app.services.tagging import add_tag, get_tag_applications, get_tags


def test_tags(db: SQLAlchemy) -> None:
    joe = User(id=1, email="joe@example.com")
    db.session.add(joe)
    db.session.flush()

    article = ArticlePost(owner=joe)
    # article.newsroom_id = 42  # source Article.id
    db.session.add(article)
    db.session.flush()

    tag_applications = get_tag_applications(article)
    assert len(tag_applications) == 0

    tag = add_tag(article, "xxx")
    db.session.add(tag)
    db.session.flush()

    tag_applications = get_tag_applications(article)
    assert len(tag_applications) == 1

    tags = get_tags(article)
    assert len(tags) == 1
    assert tags == [{"label": "xxx", "type": "manual"}]


def test_add_tag_with_type(db: SQLAlchemy) -> None:
    """Test adding a tag with a specific type."""
    joe = User(id=1, email="joe@example.com")
    db.session.add(joe)
    db.session.flush()

    article = ArticlePost(owner=joe)
    db.session.add(article)
    db.session.flush()

    tag = add_tag(article, "test-tag", type="auto")
    assert tag.type == "auto"
    assert tag.label == "test-tag"
    assert tag.object_id == article.id


def test_tag_application_repr(db: SQLAlchemy) -> None:
    """Test TagApplication __repr__ method."""
    joe = User(id=1, email="joe@example.com")
    db.session.add(joe)
    db.session.flush()

    article = ArticlePost(owner=joe)
    db.session.add(article)
    db.session.flush()

    tag = add_tag(article, "my-tag")
    db.session.add(tag)
    db.session.flush()

    repr_str = repr(tag)
    assert "TagApplication" in repr_str
    assert "'my-tag'" in repr_str
    assert str(article.id) in repr_str


def test_get_tags_with_multiple_tags(db: SQLAlchemy) -> None:
    """Test getting tags with multiple tag applications."""
    joe = User(id=1, email="joe@example.com")
    db.session.add(joe)
    db.session.flush()

    article = ArticlePost(owner=joe)
    db.session.add(article)
    db.session.flush()

    # Add multiple tags
    tag1 = add_tag(article, "tag-alpha", type="manual")
    tag2 = add_tag(article, "tag-beta", type="auto")
    tag3 = add_tag(article, "tag-gamma", type="manual")
    db.session.add_all([tag1, tag2, tag3])
    db.session.flush()

    tags = get_tags(article)
    assert len(tags) == 3

    # Should be sorted by label
    labels = [t["label"] for t in tags]
    assert labels == ["tag-alpha", "tag-beta", "tag-gamma"]


def test_get_tags_with_duplicate_labels_auto_and_manual(db: SQLAlchemy) -> None:
    """Test get_tags when same label has both auto and manual types."""
    joe = User(id=1, email="joe@example.com")
    db.session.add(joe)
    db.session.flush()

    article = ArticlePost(owner=joe)
    db.session.add(article)
    db.session.flush()

    # Add same tag twice with different types
    tag1 = add_tag(article, "duplicate", type="auto")
    tag2 = add_tag(article, "duplicate", type="manual")
    db.session.add_all([tag1, tag2])
    db.session.flush()

    tags = get_tags(article)
    assert len(tags) == 1
    # Manual should take precedence
    assert tags[0] == {"label": "duplicate", "type": "manual"}


def test_get_tags_with_multiple_auto_duplicates(db: SQLAlchemy) -> None:
    """Test get_tags when same label has multiple auto types."""
    joe = User(id=1, email="joe@example.com")
    db.session.add(joe)
    db.session.flush()

    article = ArticlePost(owner=joe)
    db.session.add(article)
    db.session.flush()

    # Add same tag multiple times as auto
    tag1 = add_tag(article, "auto-tag", type="auto")
    tag2 = add_tag(article, "auto-tag", type="auto")
    db.session.add_all([tag1, tag2])
    db.session.flush()

    tags = get_tags(article)
    assert len(tags) == 1
    assert tags[0] == {"label": "auto-tag", "type": "auto"}
