# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.orm import scoped_session

from app.models.auth import User
from app.models.lifecycle import PublicationStatus
from app.models.organisation import Organisation
from app.modules.wip.models.comroom.communique import Communique


def test_communique_basic(db_session: scoped_session) -> None:
    """Test basic Communique creation and persistence."""
    assert isinstance(db_session, scoped_session)

    joe = User(email="joe@example.com")
    my_org = Organisation(name="My Org")

    db_session.add_all([joe, my_org])
    db_session.flush()

    communique = Communique(owner=joe, publisher=my_org)

    db_session.add(communique)
    db_session.flush()

    assert communique.id is not None
    assert communique.status == PublicationStatus.DRAFT  # Default status


def test_communique_publication_workflow(db_session: scoped_session) -> None:
    """Test publication workflow: draft -> publish -> unpublish."""
    joe = User(email="joe@example.com")
    publisher = Organisation(name="Publisher Org")

    db_session.add_all([joe, publisher])
    db_session.flush()

    communique = Communique(owner=joe)
    communique.titre = "Test Communique"
    communique.contenu = "Test content"

    db_session.add(communique)
    db_session.flush()

    # Initial state: DRAFT
    assert communique.status == PublicationStatus.DRAFT
    assert communique.published_at is None

    # BUSINESS RULE: Can publish communique
    assert communique.can_publish() is True

    # Publish communique
    communique.publish(publisher_id=publisher.id)

    assert communique.status == PublicationStatus.PUBLIC
    assert communique.published_at is not None
    assert communique.publisher_id == publisher.id

    # BUSINESS RULE: Cannot publish already published communique
    assert communique.can_publish() is False

    # BUSINESS RULE: Can unpublish published communique
    assert communique.can_unpublish() is True

    # Unpublish communique
    communique.unpublish()

    assert communique.status == PublicationStatus.DRAFT
    # published_at should remain (audit trail)
    assert communique.published_at is not None

    # Can publish again after unpublishing
    assert communique.can_publish() is True


def test_communique_publication_validation(db_session: scoped_session) -> None:
    """Test publication validation rules."""
    joe = User(email="joe@example.com")

    db_session.add(joe)
    db_session.flush()

    communique = Communique(owner=joe)

    db_session.add(communique)
    db_session.flush()

    # BUSINESS RULE: Cannot publish without titre
    communique.titre = ""
    communique.contenu = "Some content"
    with pytest.raises(ValueError, match="titre"):
        communique.publish()

    # BUSINESS RULE: Cannot publish without contenu
    communique.titre = "Test Title"
    communique.contenu = ""
    with pytest.raises(ValueError, match="contenu"):
        communique.publish()

    # Valid communique can be published
    communique.contenu = "Some content"
    communique.publish()
    assert communique.status == PublicationStatus.PUBLIC


def test_communique_embargo_logic(db_session: scoped_session) -> None:
    """Test embargo logic - critical business rule for press releases."""
    joe = User(email="joe@example.com")

    db_session.add(joe)
    db_session.flush()

    communique = Communique(owner=joe)
    communique.titre = "Embargoed Communique"
    communique.contenu = "Confidential content until embargo date"

    db_session.add(communique)
    db_session.flush()

    # BUSINESS RULE: Cannot publish if embargoed_until is in the future
    future_embargo = datetime.now(UTC) + timedelta(days=7)
    communique.embargoed_until = future_embargo

    with pytest.raises(ValueError, match="embargo"):
        communique.publish()

    # BUSINESS RULE: Can publish if embargo date has passed
    past_embargo = datetime.now(UTC) - timedelta(days=1)
    communique.embargoed_until = past_embargo
    communique.publish()
    assert communique.status == PublicationStatus.PUBLIC

    # BUSINESS RULE: is_embargoed property
    communique2 = Communique(owner=joe)
    communique2.titre = "Test"
    communique2.contenu = "Content"
    db_session.add(communique2)
    db_session.flush()

    # No embargo date
    assert communique2.is_embargoed is False

    # Future embargo
    communique2.embargoed_until = datetime.now(UTC) + timedelta(hours=1)
    assert communique2.is_embargoed is True

    # Past embargo
    communique2.embargoed_until = datetime.now(UTC) - timedelta(hours=1)
    assert communique2.is_embargoed is False


def test_communique_expiration(db_session: scoped_session) -> None:
    """Test communique expiration logic."""
    joe = User(email="joe@example.com")

    db_session.add(joe)
    db_session.flush()

    communique = Communique(owner=joe)
    communique.titre = "Test Communique"
    communique.contenu = "Test content"

    db_session.add(communique)
    db_session.flush()

    # No expiration date set
    assert communique.is_expired is False

    # Set expiration in the past
    communique.expired_at = datetime.now(UTC) - timedelta(days=1)
    assert communique.is_expired is True

    # Set expiration in the future
    communique.expired_at = datetime.now(UTC) + timedelta(days=1)
    assert communique.is_expired is False


def test_communique_query_properties(db_session: scoped_session) -> None:
    """Test query properties for communique state."""
    joe = User(email="joe@example.com")

    db_session.add(joe)
    db_session.flush()

    communique = Communique(owner=joe)
    communique.titre = "Test Communique"
    communique.contenu = "Test content"

    db_session.add(communique)
    db_session.flush()

    # Draft state
    assert communique.is_draft is True
    assert communique.is_public is False

    # Publish
    communique.publish()
    assert communique.is_draft is False
    assert communique.is_public is True

    # Unpublish
    communique.unpublish()
    assert communique.is_draft is True
    assert communique.is_public is False
