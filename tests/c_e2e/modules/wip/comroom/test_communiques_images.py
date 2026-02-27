# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Integration tests for Communiques image management."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest

from app.flask.routing import url_for
from app.models.auth import User
from app.models.lifecycle import PublicationStatus
from app.models.organisation import Organisation
from app.modules.wip.crud.cbvs.communiques import CommuniquesTable, CommuniquesWipView
from app.modules.wip.models.comroom.communique import Communique

if TYPE_CHECKING:
    from flask.testing import FlaskClient
    from sqlalchemy.orm import Session


@pytest.fixture
def communique_with_title(
    db_session: Session, test_org: Organisation, test_user: User
) -> Communique:
    """Create a test communique with a title."""
    communique = Communique(owner=test_user, publisher=test_org)
    communique.titre = "Test Communique With Images"
    communique.contenu = "Content for image tests"
    communique.status = PublicationStatus.DRAFT
    db_session.add(communique)
    db_session.flush()
    return communique


class TestCommuniquesImagesPage:
    """Tests for the communique images page."""

    def test_images_page_loads(
        self, logged_in_client: FlaskClient, communique_with_title: Communique
    ):
        """Test that images page loads successfully."""
        url = url_for("CommuniquesWipView:images", id=communique_with_title.id)
        response = logged_in_client.get(url)
        assert response.status_code == 200

    def test_images_page_shows_title(
        self, logged_in_client: FlaskClient, communique_with_title: Communique
    ):
        """Test that images page shows communique title."""
        url = url_for("CommuniquesWipView:images", id=communique_with_title.id)
        response = logged_in_client.get(url)
        assert response.status_code == 200
        html = response.data.decode()
        assert communique_with_title.titre in html

    def test_images_cancel_action(
        self, logged_in_client: FlaskClient, communique_with_title: Communique
    ):
        """Test cancel action redirects to index."""
        url = url_for("CommuniquesWipView:images", id=communique_with_title.id)
        response = logged_in_client.post(
            url, data={"_action": "cancel"}, follow_redirects=False
        )
        assert response.status_code == 302

    def test_add_image_empty_fails(
        self, logged_in_client: FlaskClient, communique_with_title: Communique
    ):
        """Test adding empty image shows error."""
        url = url_for("CommuniquesWipView:images", id=communique_with_title.id)
        response = logged_in_client.post(
            url,
            data={
                "_action": "add-image",
                "caption": "Test Caption",
                "copyright": "Test Copyright",
            },
            content_type="multipart/form-data",
            follow_redirects=False,
        )
        # Should redirect back with flash message
        assert response.status_code in (302, 400)


class TestCommuniquesTable:
    """Tests for the CommuniquesTable class."""

    def test_table_id(self):
        """Test that table has correct id."""
        table = CommuniquesTable()
        assert table.id == "communiques-table"

    def test_get_columns(self):
        """Test get_columns returns expected columns."""
        table = CommuniquesTable()
        columns = table.get_columns()

        names = [c["name"] for c in columns]
        assert "titre" in names
        assert "status" in names
        assert "published_at" in names
        assert "$actions" in names

    def test_get_actions_draft(self, app):
        """Test get_actions for draft communique."""
        with app.test_request_context():
            table = CommuniquesTable()

            item = MagicMock()
            item.id = 1
            item.status = PublicationStatus.DRAFT

            actions = table.get_actions(item)
            labels = [a["label"] for a in actions]

            assert "Voir" in labels
            assert "Modifier" in labels
            assert "Images" in labels
            assert "Publier" in labels
            assert "Supprimer" in labels
            assert "Dépublier" not in labels

    def test_get_actions_published(self, app):
        """Test get_actions for published communique."""
        with app.test_request_context():
            table = CommuniquesTable()

            item = MagicMock()
            item.id = 1
            item.status = PublicationStatus.PUBLIC

            actions = table.get_actions(item)
            labels = [a["label"] for a in actions]

            assert "Dépublier" in labels
            assert "Publier" not in labels


class TestCommuniquesWipViewAttributes:
    """Tests for CommuniquesWipView class attributes."""

    def test_view_attributes(self):
        """Test view has expected attributes."""
        assert CommuniquesWipView.name == "communiques"
        assert CommuniquesWipView.route_base == "communiques"
        assert CommuniquesWipView.icon == "megaphone"
        assert CommuniquesWipView.table_id == "communique-table-body"

    def test_view_labels(self):
        """Test view has expected labels."""
        assert "communiqué" in CommuniquesWipView.label_main.lower()
        assert "communiqué" in CommuniquesWipView.label_new.lower()
        assert "communiqué" in CommuniquesWipView.label_edit.lower()
        assert "communiqué" in CommuniquesWipView.label_view.lower()
