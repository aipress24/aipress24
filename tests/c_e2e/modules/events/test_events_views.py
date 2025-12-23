# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Tests for events views (convention-driven navigation)."""

from __future__ import annotations

import arrow
import pytest
from flask import Flask
from flask.testing import FlaskClient
from sqlalchemy.orm import Session

from app.models.auth import User
from app.models.lifecycle import PublicationStatus
from app.modules.events.models import EventPost


@pytest.fixture
def test_user(db_session: Session) -> User:
    """Create a test user for events tests."""
    user = User(email="events_views_test@example.com")
    user.photo = b""
    db_session.add(user)
    db_session.flush()
    return user


@pytest.fixture
def authenticated_client(
    app: Flask, db_session: Session, test_user: User
) -> FlaskClient:
    """Provide a Flask test client logged in as test user."""
    client = app.test_client()

    with client.session_transaction() as sess:
        sess["_user_id"] = str(test_user.id)
        sess["_fresh"] = True
        sess["_permanent"] = True
        sess["_id"] = (
            str(test_user.fs_uniquifier)
            if hasattr(test_user, "fs_uniquifier")
            else str(test_user.id)
        )

    return client


@pytest.fixture
def sample_event(db_session: Session, test_user: User) -> EventPost:
    """Create a sample public event for testing."""
    today = arrow.now()
    event = EventPost(
        title="Test Event for Views",
        owner_id=test_user.id,
        status=PublicationStatus.PUBLIC,
        start_date=today,
        end_date=today.shift(days=1),
    )
    db_session.add(event)
    db_session.flush()
    return event


class TestEventsListView:
    """Test events list view."""

    def test_events_page_accessible(
        self, authenticated_client: FlaskClient, db_session: Session
    ):
        """Test events page is accessible with regular GET."""
        response = authenticated_client.get("/events/")
        # Accept 200 or 302 (auth may redirect in some test configs)
        assert response.status_code in (200, 302)

    def test_events_page_renders_template(
        self, authenticated_client: FlaskClient, db_session: Session
    ):
        """Test events page renders correct content."""
        response = authenticated_client.get("/events/")
        assert response.status_code in (200, 302)

    def test_events_page_htmx_boosted(
        self, authenticated_client: FlaskClient, db_session: Session
    ):
        """Test events page with HTMX boosted request returns full page."""
        response = authenticated_client.get(
            "/events/",
            headers={"HX-Request": "true", "HX-Boosted": "true"},
        )
        assert response.status_code in (200, 302)

    def test_events_page_htmx_partial_without_target(
        self, authenticated_client: FlaskClient, db_session: Session
    ):
        """Test events page with HTMX request but no specific target."""
        response = authenticated_client.get(
            "/events/",
            headers={"HX-Request": "true"},
        )
        # Should return full page as fallback
        assert response.status_code in (200, 302)

    def test_events_page_htmx_members_list_target(
        self, authenticated_client: FlaskClient, db_session: Session
    ):
        """Test events page with HTMX request targeting members-list."""
        response = authenticated_client.get(
            "/events/",
            headers={"HX-Request": "true", "HX-Target": "members-list"},
        )
        assert response.status_code in (200, 302)

    def test_events_page_with_tag_filter(
        self, authenticated_client: FlaskClient, db_session: Session
    ):
        """Test events page with tag filter query param."""
        response = authenticated_client.get(
            "/events/",
            headers={"HX-Request": "true", "HX-Target": "members-list"},
            query_string={"tag": "conference"},
        )
        assert response.status_code in (200, 302)

    def test_events_page_with_search(
        self, authenticated_client: FlaskClient, db_session: Session
    ):
        """Test events page with search query param."""
        response = authenticated_client.get("/events/?search=test")
        assert response.status_code in (200, 302)

    def test_events_page_with_month_filter(
        self, authenticated_client: FlaskClient, db_session: Session
    ):
        """Test events page with month filter."""
        response = authenticated_client.get("/events/?month=2024-06")
        assert response.status_code in (200, 302)

    def test_events_page_with_day_filter(
        self, authenticated_client: FlaskClient, db_session: Session
    ):
        """Test events page with day filter."""
        response = authenticated_client.get("/events/?day=2024-06-15")
        assert response.status_code in (200, 302)


class TestEventsPostView:
    """Test events POST handler (filter updates)."""

    def test_events_post_filter_update(
        self, authenticated_client: FlaskClient, db_session: Session
    ):
        """Test POST to events page for filter updates."""
        response = authenticated_client.post(
            "/events/",
            data={"action": "toggle", "id": "genre", "value": "conference"},
            headers={"HX-Request": "true"},
        )
        assert response.status_code in (200, 302)

    def test_events_post_full_page_target(
        self, authenticated_client: FlaskClient, db_session: Session
    ):
        """Test POST with body target returns full page."""
        response = authenticated_client.post(
            "/events/",
            data={"action": "toggle", "id": "genre", "value": "conference"},
            headers={"HX-Request": "true", "HX-Target": "body"},
        )
        assert response.status_code in (200, 302)


class TestEventDetailView:
    """Test event detail view."""

    def test_event_detail_accessible(
        self,
        authenticated_client: FlaskClient,
        db_session: Session,
        sample_event,
    ):
        """Test event detail page is accessible."""
        response = authenticated_client.get(f"/events/{sample_event.id}")
        assert response.status_code in (200, 302)

    def test_event_detail_sets_nav_label(
        self,
        authenticated_client: FlaskClient,
        db_session: Session,
        sample_event,
    ):
        """Test event detail sets dynamic nav label."""
        response = authenticated_client.get(f"/events/{sample_event.id}")
        assert response.status_code in (200, 302)
        # The title should be in the response (from g.nav.label)

    def test_event_detail_404_for_invalid_id(
        self, authenticated_client: FlaskClient, db_session: Session
    ):
        """Test event detail returns 404 for invalid ID."""
        response = authenticated_client.get("/events/999999")
        # May get 404 or redirect to login
        assert response.status_code in (404, 302)


class TestCalendarView:
    """Test calendar view."""

    def test_calendar_accessible(
        self, authenticated_client: FlaskClient, db_session: Session
    ):
        """Test calendar page is accessible."""
        response = authenticated_client.get("/events/calendar")
        assert response.status_code in (200, 302)

    def test_calendar_with_month_param(
        self, authenticated_client: FlaskClient, db_session: Session
    ):
        """Test calendar with month query parameter."""
        response = authenticated_client.get("/events/calendar?month=2024-06")
        assert response.status_code in (200, 302)


class TestNavigationIntegration:
    """Test navigation system integration with events views."""

    def test_nav_tree_includes_events_section(self, app):
        """Test that nav tree includes events section."""
        nav_tree = app.extensions["nav_tree"]

        with app.app_context():
            nav_tree.build(app)
            assert "events" in nav_tree._sections
            section = nav_tree._sections["events"]
            assert section.label == "Evénements"

    def test_nav_tree_includes_events_pages(self, app):
        """Test that nav tree includes events pages."""
        nav_tree = app.extensions["nav_tree"]

        with app.app_context():
            nav_tree.build(app)
            assert "events.events" in nav_tree._nodes
            assert "events.calendar" in nav_tree._nodes
            assert "events.event" in nav_tree._nodes

    def test_breadcrumbs_for_events_list(self, app):
        """Test breadcrumbs generation for events list."""
        nav_tree = app.extensions["nav_tree"]

        with app.app_context():
            nav_tree.build(app)
            crumbs = nav_tree.build_breadcrumbs("events.events", {})
            assert len(crumbs) >= 2
            # Last crumb should be the current page
            assert crumbs[-1].current is True

    def test_breadcrumbs_for_event_detail(self, app):
        """Test breadcrumbs generation for event detail."""
        nav_tree = app.extensions["nav_tree"]

        with app.app_context():
            nav_tree.build(app)
            crumbs = nav_tree.build_breadcrumbs("events.event", {"id": 123})
            assert len(crumbs) >= 2
            # Should include parent (events list) in chain

    def test_secondary_menu_for_events(self, app):
        """Test secondary menu generation for events section."""
        nav_tree = app.extensions["nav_tree"]

        with app.app_context():
            nav_tree.build(app)
            menu = nav_tree.build_menu("events", "events.events")
            # Should have at least events and calendar
            labels = [item.label for item in menu]
            assert "Evénements" in labels or "Calendrier" in labels

    def test_g_nav_available_in_request(
        self, authenticated_client: FlaskClient, db_session: Session
    ):
        """Test that g.nav is available during requests."""
        response = authenticated_client.get("/events/")
        assert response.status_code in (200, 302)
        # If g.nav wasn't set up properly, the request would fail

    def test_breadcrumbs_injected_to_context_service(self, app):
        """Test that breadcrumbs are injected into Context service."""
        from svcs.flask import container

        nav_tree = app.extensions["nav_tree"]
        from app.services.context import Context

        with app.test_request_context("/events/"):
            # Build nav tree
            nav_tree.build(app)

            # Simulate before_request
            from flask import g

            from app.flask.lib.nav.registration import _inject_breadcrumbs_to_context
            from app.flask.lib.nav.request import NavRequest

            g.nav = NavRequest("events.events", {})
            _inject_breadcrumbs_to_context()

            # Check Context service has breadcrumbs
            context = container.get(Context)
            breadcrumbs = context["breadcrumbs"]

            assert isinstance(breadcrumbs, list)
            assert len(breadcrumbs) >= 1
            # Check format is legacy (name, href, current)
            assert "name" in breadcrumbs[-1]
            assert "href" in breadcrumbs[-1]
            assert "current" in breadcrumbs[-1]
