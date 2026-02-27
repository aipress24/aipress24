# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Integration tests for Events image management."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from app.flask.routing import url_for
from app.models.auth import User
from app.models.lifecycle import PublicationStatus
from app.models.organisation import Organisation
from app.modules.wip.models.eventroom import Event

if TYPE_CHECKING:
    from flask.testing import FlaskClient
    from sqlalchemy.orm import Session


@pytest.fixture
def event_with_title(
    db_session: Session, test_org: Organisation, test_user: User
) -> Event:
    """Create a test event with a title."""
    event = Event(owner=test_user, publisher=test_org)
    event.titre = "Test Event With Images"
    event.contenu = "Content for image tests"
    event.status = PublicationStatus.DRAFT
    db_session.add(event)
    db_session.flush()
    return event


@pytest.fixture
def published_event(
    db_session: Session, test_org: Organisation, test_user: User
) -> Event:
    """Create a published event."""
    event = Event(owner=test_user, publisher=test_org)
    event.titre = "Published Event"
    event.contenu = "Published content"
    event.status = PublicationStatus.DRAFT
    event.publish(publisher_id=test_org.id)
    db_session.add(event)
    db_session.flush()
    return event


class TestEventsIndex:
    """Tests for the events index view."""

    def test_index_loads(
        self, logged_in_client: FlaskClient, event_with_title: Event
    ):
        """Test that index page loads successfully."""
        assert event_with_title is not None
        url = url_for("EventsWipView:index")
        response = logged_in_client.get(url)
        assert response.status_code == 200


class TestEventsImagesPage:
    """Tests for the event images page."""

    def test_images_page_loads(
        self, logged_in_client: FlaskClient, event_with_title: Event
    ):
        """Test that images page loads successfully."""
        url = url_for("EventsWipView:images", id=event_with_title.id)
        response = logged_in_client.get(url)
        assert response.status_code == 200

    def test_images_page_shows_title(
        self, logged_in_client: FlaskClient, event_with_title: Event
    ):
        """Test that images page shows event title."""
        url = url_for("EventsWipView:images", id=event_with_title.id)
        response = logged_in_client.get(url)
        assert response.status_code == 200
        html = response.data.decode()
        assert event_with_title.titre in html

    def test_images_cancel_action(
        self, logged_in_client: FlaskClient, event_with_title: Event
    ):
        """Test cancel action redirects to index."""
        url = url_for("EventsWipView:images", id=event_with_title.id)
        response = logged_in_client.post(
            url, data={"_action": "cancel"}, follow_redirects=False
        )
        assert response.status_code == 302


class TestEventsPublishWorkflow:
    """Tests for event publish/unpublish workflow."""

    def test_publish_event(
        self, logged_in_client: FlaskClient, event_with_title: Event
    ):
        """Test publishing an event."""
        url = url_for("EventsWipView:publish", id=event_with_title.id)
        response = logged_in_client.get(url, follow_redirects=False)
        assert response.status_code == 302

    def test_unpublish_event(
        self, logged_in_client: FlaskClient, published_event: Event
    ):
        """Test unpublishing an event."""
        url = url_for("EventsWipView:unpublish", id=published_event.id)
        response = logged_in_client.get(url, follow_redirects=False)
        assert response.status_code == 302

    def test_unpublish_draft_event(
        self, logged_in_client: FlaskClient, event_with_title: Event
    ):
        """Test that unpublishing a draft fails."""
        url = url_for("EventsWipView:unpublish", id=event_with_title.id)
        response = logged_in_client.get(url, follow_redirects=False)
        assert response.status_code == 302


class TestEventsCRUD:
    """Tests for basic CRUD operations on events."""

    def test_get_event_detail(
        self, logged_in_client: FlaskClient, event_with_title: Event
    ):
        """Test viewing event detail."""
        url = url_for("EventsWipView:get", id=event_with_title.id)
        response = logged_in_client.get(url)
        assert response.status_code == 200

    def test_edit_event_form(
        self, logged_in_client: FlaskClient, event_with_title: Event
    ):
        """Test loading event edit form."""
        url = url_for("EventsWipView:edit", id=event_with_title.id)
        response = logged_in_client.get(url)
        assert response.status_code == 200

    def test_create_event_form(
        self, logged_in_client: FlaskClient, test_user: User
    ):
        """Test loading event creation form."""
        assert test_user is not None
        url = url_for("EventsWipView:new")
        response = logged_in_client.get(url)
        assert response.status_code == 200


class TestEventsTable:
    """Tests for the EventsTable class."""

    def test_table_id(self):
        """Test that table has correct id."""
        from app.modules.wip.crud.cbvs.events import EventsTable

        table = EventsTable()
        assert table.id == "events-table"

    def test_get_actions_draft(self, app):
        """Test get_actions for draft event."""
        from app.modules.wip.crud.cbvs.events import EventsTable
        from app.models.lifecycle import PublicationStatus
        from unittest.mock import MagicMock

        with app.test_request_context():
            table = EventsTable()

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
        """Test get_actions for published event."""
        from app.modules.wip.crud.cbvs.events import EventsTable
        from app.models.lifecycle import PublicationStatus
        from unittest.mock import MagicMock

        with app.test_request_context():
            table = EventsTable()

            item = MagicMock()
            item.id = 1
            item.status = PublicationStatus.PUBLIC

            actions = table.get_actions(item)
            labels = [a["label"] for a in actions]

            assert "Dépublier" in labels
            assert "Publier" not in labels


class TestEventsWipViewAttributes:
    """Tests for EventsWipView class attributes."""

    def test_view_attributes(self):
        """Test view has expected attributes."""
        from app.modules.wip.crud.cbvs.events import EventsWipView

        assert EventsWipView.name == "events"
        assert EventsWipView.route_base == "events"
        assert EventsWipView.icon == "calendar"
        assert EventsWipView.table_id == "events-table-body"

    def test_view_labels(self):
        """Test view has expected labels."""
        from app.modules.wip.crud.cbvs.events import EventsWipView

        # Note: label_main is plural "Evénements"
        assert "vénement" in EventsWipView.label_main.lower()
        assert "vénement" in EventsWipView.label_new.lower()
        assert "vénement" in EventsWipView.label_edit.lower()
        assert "vénement" in EventsWipView.label_view.lower()
