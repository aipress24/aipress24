# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import arrow
import pytest
from sqlalchemy.orm import scoped_session

from app.models.auth import User
from app.models.lifecycle import PublicationStatus
from app.models.organisation import Organisation
from app.modules.wip.models.newsroom.article import Article


def test_article_basic(db_session: scoped_session) -> None:
    """Test basic Article creation and persistence."""
    assert isinstance(db_session, scoped_session)

    joe = User(email="joe@example.com")
    jim = User(email="jim@example.com")

    media = Organisation(name="Le Journal")

    db_session.add_all([joe, jim, media])
    db_session.flush()

    article = Article(owner=jim, media=media)
    article.date_parution_prevue = arrow.get("2022-01-01").datetime
    article.date_publication_aip24 = arrow.get("2022-01-01").datetime

    # commanditaire_id is the "commissioning editor" - required field
    article.commanditaire_id = joe.id

    db_session.add(article)
    db_session.flush()

    assert article.id is not None
    assert article.status == PublicationStatus.DRAFT  # Default status


def test_article_publication_workflow(db_session: scoped_session) -> None:
    """Test publication workflow: draft -> publish -> unpublish."""
    joe = User(email="joe@example.com")
    media = Organisation(name="Le Journal")
    publisher = Organisation(name="Publisher Org")

    db_session.add_all([joe, media, publisher])
    db_session.flush()

    article = Article(owner=joe, media=media)
    article.titre = "Test Article"
    article.contenu = "Test content"
    article.date_parution_prevue = arrow.get("2025-12-01").datetime
    article.commanditaire_id = joe.id

    db_session.add(article)
    db_session.flush()

    # Initial state: DRAFT
    assert article.status == PublicationStatus.DRAFT
    assert article.published_at is None

    # BUSINESS RULE: Can publish article
    assert article.can_publish() is True

    # Publish article
    article.publish(publisher_id=publisher.id)

    assert article.status == PublicationStatus.PUBLIC
    assert article.published_at is not None
    assert article.publisher_id == publisher.id

    # BUSINESS RULE: Cannot publish already published article
    assert article.can_publish() is False

    # BUSINESS RULE: Can unpublish published article
    assert article.can_unpublish() is True

    # Unpublish article
    article.unpublish()

    assert article.status == PublicationStatus.DRAFT
    # published_at should remain (audit trail)
    assert article.published_at is not None

    # Can publish again after unpublishing
    assert article.can_publish() is True


def test_article_publication_validation(db_session: scoped_session) -> None:
    """Test publication validation rules."""
    joe = User(email="joe@example.com")
    media = Organisation(name="Le Journal")

    db_session.add_all([joe, media])
    db_session.flush()

    article = Article(owner=joe, media=media)
    article.commanditaire_id = joe.id
    article.date_parution_prevue = arrow.get("2025-12-01").datetime

    db_session.add(article)
    db_session.flush()

    # BUSINESS RULE: Cannot publish without titre
    article.titre = ""
    article.contenu = "Some content"
    with pytest.raises(ValueError, match="titre"):
        article.publish()

    # BUSINESS RULE: Cannot publish without contenu
    article.titre = "Test Title"
    article.contenu = ""
    with pytest.raises(ValueError, match="contenu"):
        article.publish()

    # Valid article can be published
    article.contenu = "Some content"
    article.publish()
    assert article.status == PublicationStatus.PUBLIC


def test_article_expiration(db_session: scoped_session) -> None:
    """Test article expiration logic."""
    joe = User(email="joe@example.com")
    media = Organisation(name="Le Journal")

    db_session.add_all([joe, media])
    db_session.flush()

    article = Article(owner=joe, media=media)
    article.titre = "Test Article"
    article.contenu = "Test content"
    article.date_parution_prevue = arrow.get("2025-12-01").datetime
    article.commanditaire_id = joe.id

    db_session.add(article)
    db_session.flush()

    # No expiration date set
    assert article.is_expired is False

    # Set expiration in the past
    article.expired_at = datetime.now(timezone.utc) - timedelta(days=1)
    assert article.is_expired is True

    # Set expiration in the future
    article.expired_at = datetime.now(timezone.utc) + timedelta(days=1)
    assert article.is_expired is False


def test_article_query_properties(db_session: scoped_session) -> None:
    """Test query properties for article state."""
    joe = User(email="joe@example.com")
    media = Organisation(name="Le Journal")

    db_session.add_all([joe, media])
    db_session.flush()

    article = Article(owner=joe, media=media)
    article.titre = "Test Article"
    article.contenu = "Test content"
    article.date_parution_prevue = arrow.get("2025-12-01").datetime
    article.commanditaire_id = joe.id

    db_session.add(article)
    db_session.flush()

    # Draft state
    assert article.is_draft is True
    assert article.is_public is False

    # Publish
    article.publish()
    assert article.is_draft is False
    assert article.is_public is True

    # Unpublish
    article.unpublish()
    assert article.is_draft is True
    assert article.is_public is False
