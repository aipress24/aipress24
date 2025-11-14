# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Integration tests for Communiques WIP views."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

import pytest

from app.flask.routing import url_for
from app.models.auth import User
from app.models.lifecycle import PublicationStatus
from app.models.organisation import Organisation
from app.modules.wip.models.comroom.communique import Communique

if TYPE_CHECKING:
    from flask.testing import FlaskClient
    from sqlalchemy.orm import Session


@pytest.fixture
def test_user(db_session: Session) -> User:
    """Get the test user (ID 0 created by logged_in_client fixture)."""
    user = db_session.query(User).filter_by(id=0).first()
    if not user:
        msg = "Test user (ID 0) not found. Ensure logged_in_client fixture is used."
        raise RuntimeError(msg)
    return user


@pytest.fixture
def test_org(db_session: Session, test_user: User) -> Organisation:
    """Get the test organisation (from user ID 0)."""
    if not test_user.organisation:
        msg = "Test user (ID 0) has no organisation."
        raise RuntimeError(msg)
    return test_user.organisation


@pytest.fixture
def test_communique(
    db_session: Session, test_org: Organisation, test_user: User
) -> Communique:
    """Create a test communique in DRAFT status."""
    communique = Communique(owner=test_user, publisher=test_org)
    communique.titre = "Test Press Release"
    communique.contenu = "Press release content"
    communique.status = PublicationStatus.DRAFT
    db_session.add(communique)
    db_session.flush()
    return communique


@pytest.fixture
def embargoed_communique(
    db_session: Session, test_org: Organisation, test_user: User
) -> Communique:
    """Create a communique under embargo."""
    communique = Communique(owner=test_user, publisher=test_org)
    communique.titre = "Embargoed Press Release"
    communique.contenu = "Confidential content"
    communique.status = PublicationStatus.DRAFT
    # Set embargo to future date
    communique.embargoed_until = datetime.now(UTC) + timedelta(days=7)
    db_session.add(communique)
    db_session.flush()
    return communique


@pytest.fixture
def published_communique(
    db_session: Session, test_org: Organisation, test_user: User
) -> Communique:
    """Create a published communique."""
    communique = Communique(owner=test_user, publisher=test_org)
    communique.titre = "Published Press Release"
    communique.contenu = "Public content"
    communique.status = PublicationStatus.DRAFT
    communique.publish(publisher_id=test_org.id)
    db_session.add(communique)
    db_session.flush()
    return communique


class TestCommuniquesIndex:
    """Tests for the communiques index view."""

    def test_index_loads_successfully(
        self, logged_in_client: FlaskClient, test_communique: Communique
    ):
        """Test that index page loads successfully for authenticated user."""
        assert test_communique is not None  # Ensure fixture is used
        url = url_for("CommuniquesWipView:index")
        response = logged_in_client.get(url)
        assert response.status_code == 200


class TestCommuniquesPublish:
    """Tests for the communique publish workflow."""

    def test_publish_communique_success(
        self,
        logged_in_client: FlaskClient,
        test_communique: Communique,
    ):
        """Test successfully publishing a draft communique."""
        url = url_for("CommuniquesWipView:publish", id=test_communique.id)
        response = logged_in_client.get(url, follow_redirects=False)
        assert response.status_code == 302

    def test_publish_embargoed_communique_fails(
        self,
        logged_in_client: FlaskClient,
        embargoed_communique: Communique,
    ):
        """Test that publishing an embargoed communique fails."""
        url = url_for("CommuniquesWipView:publish", id=embargoed_communique.id)
        response = logged_in_client.get(url, follow_redirects=False)

        # Should redirect back with error
        assert response.status_code == 302

        # Verify embargo is still active
        assert embargoed_communique.is_embargoed is True

    def test_publish_communique_without_titre(
        self,
        logged_in_client: FlaskClient,
        db_session: Session,
        test_user: User,
        test_org: Organisation,
    ):
        """Test that publishing fails without titre."""
        communique = Communique(owner=test_user, publisher=test_org)
        communique.titre = ""  # Empty titre
        communique.contenu = "Some content"
        communique.status = PublicationStatus.DRAFT
        db_session.add(communique)
        db_session.flush()

        url = url_for("CommuniquesWipView:publish", id=communique.id)
        response = logged_in_client.get(url, follow_redirects=False)
        assert response.status_code == 302

    def test_publish_communique_without_contenu(
        self,
        logged_in_client: FlaskClient,
        db_session: Session,
        test_user: User,
        test_org: Organisation,
    ):
        """Test that publishing fails without contenu."""
        communique = Communique(owner=test_user, publisher=test_org)
        communique.titre = "Test Title"
        communique.contenu = ""  # Empty contenu
        communique.status = PublicationStatus.DRAFT
        db_session.add(communique)
        db_session.flush()

        url = url_for("CommuniquesWipView:publish", id=communique.id)
        response = logged_in_client.get(url, follow_redirects=False)
        assert response.status_code == 302


class TestCommuniquesUnpublish:
    """Tests for the communique unpublish workflow."""

    def test_unpublish_communique_success(
        self, logged_in_client: FlaskClient, published_communique: Communique
    ):
        """Test successfully unpublishing a published communique."""
        url = url_for("CommuniquesWipView:unpublish", id=published_communique.id)
        response = logged_in_client.get(url, follow_redirects=False)
        assert response.status_code == 302

    def test_unpublish_draft_communique(
        self, logged_in_client: FlaskClient, test_communique: Communique
    ):
        """Test that unpublishing a draft communique fails."""
        url = url_for("CommuniquesWipView:unpublish", id=test_communique.id)
        response = logged_in_client.get(url, follow_redirects=False)
        assert response.status_code == 302


class TestCommuniquesCRUD:
    """Tests for basic CRUD operations on communiques."""

    def test_get_communique_detail(
        self, logged_in_client: FlaskClient, test_communique: Communique
    ):
        """Test viewing communique detail."""
        url = url_for("CommuniquesWipView:get", id=test_communique.id)
        response = logged_in_client.get(url)
        assert response.status_code == 200

    def test_edit_communique_form(
        self, logged_in_client: FlaskClient, test_communique: Communique
    ):
        """Test loading communique edit form."""
        url = url_for("CommuniquesWipView:edit", id=test_communique.id)
        response = logged_in_client.get(url)
        assert response.status_code == 200

    def test_create_communique_form(
        self, logged_in_client: FlaskClient, test_user: User
    ):
        """Test loading communique creation form."""
        assert test_user is not None  # Ensure fixture is used
        url = url_for("CommuniquesWipView:new")
        response = logged_in_client.get(url)
        assert response.status_code == 200


class TestCommuniquesEmbargo:
    """Tests for communique embargo functionality."""

    def test_embargo_validation(self, test_communique: Communique):
        """Test embargo business logic."""
        # No embargo set
        assert test_communique.is_embargoed is False

        # Set future embargo
        test_communique.embargoed_until = datetime.now(UTC) + timedelta(hours=1)
        assert test_communique.is_embargoed is True

        # Set past embargo
        test_communique.embargoed_until = datetime.now(UTC) - timedelta(hours=1)
        assert test_communique.is_embargoed is False

    def test_cannot_publish_embargoed_communique(
        self, embargoed_communique: Communique
    ):
        """Test that embargoed communique cannot be published."""
        with pytest.raises(ValueError, match="embargo"):
            embargoed_communique.publish()

    def test_can_publish_after_embargo_expires(self, embargoed_communique: Communique):
        """Test that communique can be published after embargo expires."""
        # Set embargo to past
        embargoed_communique.embargoed_until = datetime.now(UTC) - timedelta(days=1)

        # Should be able to publish now
        embargoed_communique.publish()
        assert embargoed_communique.status == PublicationStatus.PUBLIC


class TestCommuniquesValidation:
    """Tests for communique validation logic."""

    def test_communique_status_properties(self, test_communique: Communique):
        """Test communique status query properties."""
        # Draft communique
        assert test_communique.is_draft is True
        assert test_communique.is_public is False

        # Publish it
        test_communique.publish()
        assert test_communique.is_draft is False
        assert test_communique.is_public is True

        # Unpublish it
        test_communique.unpublish()
        assert test_communique.is_draft is True
        assert test_communique.is_public is False

    def test_communique_can_publish_logic(self, test_communique: Communique):
        """Test can_publish business logic."""
        # Draft communique can be published
        assert test_communique.can_publish() is True

        # Published communique cannot be published again
        test_communique.publish()
        assert test_communique.can_publish() is False

    def test_communique_can_unpublish_logic(self, test_communique: Communique):
        """Test can_unpublish business logic."""
        # Draft communique cannot be unpublished
        assert test_communique.can_unpublish() is False

        # Published communique can be unpublished
        test_communique.publish()
        assert test_communique.can_unpublish() is True
