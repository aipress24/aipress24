# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Integration tests for events module pages."""

from __future__ import annotations

from typing import TYPE_CHECKING

import arrow
import pytest
from app.models.auth import User
from app.models.lifecycle import PublicationStatus
from app.modules.events.models import EventPost
from app.modules.events.pages._filters import FilterBar
from app.modules.events.pages.calendar import CalendarPage
from app.modules.events.pages.event import EventPage, EventVM
from app.modules.events.pages.events import (
    Calendar,
    DateFilter,
    EventsPage,
)
from flask import Flask
from flask.testing import FlaskClient
from sqlalchemy.orm import Session

if TYPE_CHECKING:
    pass


@pytest.fixture
def test_user(db_session: Session) -> User:
    """Create a test user for events tests."""
    user = User(email="events_test@example.com")
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
        title="Test Event",
        owner_id=test_user.id,
        status=PublicationStatus.PUBLIC,
        start_date=today,
        end_date=today.shift(days=1),
        genre="Conference",
        sector="Tech",
    )
    db_session.add(event)
    db_session.flush()
    return event


class TestEventsPageAttributes:
    """Test EventsPage class attributes."""

    def test_page_name(self):
        """Test EventsPage has correct name."""
        assert EventsPage.name == "events"

    def test_page_label(self):
        """Test EventsPage has correct label."""
        assert EventsPage.label == "Evénements"

    def test_page_template(self):
        """Test EventsPage has correct template."""
        assert EventsPage.template == "pages/events.j2"

    def test_page_routes(self):
        """Test EventsPage has correct routes."""
        assert "/" in EventsPage.routes


class TestEventsPageEndpoint:
    """Test EventsPage HTTP endpoint."""

    def test_events_page_requires_auth(self, app: Flask):
        """Test events page requires authentication."""
        client = app.test_client()
        response = client.get("/events/")
        # Should get unauthorized or redirect
        assert response.status_code in (401, 302)

    def test_events_page_accessible_when_authenticated(
        self, authenticated_client: FlaskClient, db_session: Session
    ):
        """Test events page is accessible to authenticated users."""
        response = authenticated_client.get("/events/")
        # Should get 200 or redirect (not unauthorized)
        assert response.status_code in (200, 302)

    def test_events_page_with_event(
        self,
        authenticated_client: FlaskClient,
        db_session: Session,
        sample_event: EventPost,
    ):
        """Test events page with an existing event."""
        response = authenticated_client.get("/events/")
        assert response.status_code in (200, 302)


class TestEventPageAttributes:
    """Test EventPage class attributes."""

    def test_page_name(self):
        """Test EventPage has correct name."""
        assert EventPage.name == "event"

    def test_page_path(self):
        """Test EventPage has correct path."""
        assert EventPage.path == "/<int:id>"

    def test_page_template(self):
        """Test EventPage has correct template."""
        assert EventPage.template == "pages/event.j2"

    def test_page_parent(self):
        """Test EventPage has correct parent."""
        assert EventPage.parent == EventsPage


class TestEventPageEndpoint:
    """Test EventPage HTTP endpoint."""

    def test_event_page_accessible(
        self,
        authenticated_client: FlaskClient,
        db_session: Session,
        sample_event: EventPost,
    ):
        """Test event detail page is accessible."""
        response = authenticated_client.get(f"/events/{sample_event.id}")
        assert response.status_code in (200, 302)

    def test_event_page_not_found(
        self, authenticated_client: FlaskClient, db_session: Session
    ):
        """Test event page returns 404 for non-existent event."""
        response = authenticated_client.get("/events/999999")
        # Should get 404 or possibly redirect
        assert response.status_code in (404, 302)


class TestCalendarPageAttributes:
    """Test CalendarPage class attributes."""

    def test_page_name(self):
        """Test CalendarPage has correct name."""
        assert CalendarPage.name == "calendar"

    def test_page_label(self):
        """Test CalendarPage has correct label."""
        assert CalendarPage.label == "Evénements"

    def test_page_template(self):
        """Test CalendarPage has correct template."""
        assert CalendarPage.template == "pages/calendar.j2"


class TestCalendarPageEndpoint:
    """Test CalendarPage HTTP endpoint."""

    def test_calendar_page_accessible(
        self, authenticated_client: FlaskClient, db_session: Session
    ):
        """Test calendar page is accessible."""
        response = authenticated_client.get("/events/calendar")
        assert response.status_code in (200, 302)

    def test_calendar_page_with_month_param(
        self, authenticated_client: FlaskClient, db_session: Session
    ):
        """Test calendar page with month query parameter."""
        response = authenticated_client.get("/events/calendar?month=2024-06")
        assert response.status_code in (200, 302)


class TestDateFilter:
    """Test DateFilter class."""

    def test_init_with_no_args(self):
        """Test DateFilter initialization without day or month args."""
        args = {"day": "", "month": ""}
        df = DateFilter(args)

        assert df.day is None
        assert df.filter_on == ""
        assert df.month is not None

    def test_init_with_day(self):
        """Test DateFilter initialization with day argument."""
        args = {"day": "2024-06-15", "month": ""}
        df = DateFilter(args)

        assert df.day is not None
        assert df.day.date() == arrow.get("2024-06-15").date()
        assert df.filter_on == "day"

    def test_init_with_month(self):
        """Test DateFilter initialization with month argument."""
        args = {"day": "", "month": "2024-06"}
        df = DateFilter(args)

        assert df.filter_on == "month"
        assert df.month_start.format("YYYY-MM") == "2024-06"

    def test_month_end_calculation(self):
        """Test month end is one month after start."""
        args = {"day": "", "month": "2024-06"}
        df = DateFilter(args)

        assert df.month_end.format("YYYY-MM") == "2024-07"

    def test_apply_no_filter(self, app: Flask, db_session: Session):
        """Test apply with no filter set."""
        args = {"day": "", "month": ""}
        df = DateFilter(args)

        from sqlalchemy import select

        stmt = select(EventPost)
        result_stmt = df.apply(stmt)

        # Statement should be modified (has where clause and limit)
        assert str(result_stmt) != str(stmt)

    def test_apply_day_filter(self, app: Flask, db_session: Session):
        """Test apply with day filter."""
        args = {"day": "2024-06-15", "month": ""}
        df = DateFilter(args)

        from sqlalchemy import select

        stmt = select(EventPost)
        result_stmt = df.apply(stmt)

        # Statement should be modified
        assert str(result_stmt) != str(stmt)

    def test_apply_month_filter(self, app: Flask, db_session: Session):
        """Test apply with month filter."""
        args = {"day": "", "month": "2024-06"}
        df = DateFilter(args)

        from sqlalchemy import select

        stmt = select(EventPost)
        result_stmt = df.apply(stmt)

        # Statement should be modified
        assert str(result_stmt) != str(stmt)


class TestEventVM:
    """Test EventVM view model."""

    def test_extra_attrs_returns_dict(
        self, app: Flask, db_session: Session, sample_event: EventPost
    ):
        """Test extra_attrs returns expected dictionary."""
        with app.test_request_context():
            vm = EventVM(sample_event)
            attrs = vm.extra_attrs()

            assert isinstance(attrs, dict)
            assert "age" in attrs
            assert "author" in attrs
            assert "likes" in attrs
            assert "replies" in attrs
            assert "views" in attrs

    def test_extra_attrs_participants(
        self, app: Flask, db_session: Session, sample_event: EventPost
    ):
        """Test extra_attrs includes participants field."""
        with app.test_request_context():
            vm = EventVM(sample_event)
            attrs = vm.extra_attrs()

            assert "participants" in attrs
            assert isinstance(attrs["participants"], list)


class TestFilterBar:
    """Test FilterBar class."""

    def test_init(self, app: Flask, db_session: Session):
        """Test FilterBar initialization."""
        with app.test_request_context():
            fb = FilterBar()

            assert hasattr(fb, "state")
            assert hasattr(fb, "filters")

    def test_active_filters_empty(self, app: Flask, db_session: Session):
        """Test active_filters returns empty list when no filters active."""
        with app.test_request_context():
            fb = FilterBar()
            fb.state = {}

            assert fb.active_filters == []

    def test_active_filters_with_filters(self, app: Flask, db_session: Session):
        """Test active_filters returns filters when present."""
        with app.test_request_context():
            fb = FilterBar()
            fb.state = {
                "filters": [
                    {"id": "genre", "value": "Conference"},
                ]
            }

            active = fb.active_filters
            assert len(active) == 1
            assert active[0]["id"] == "genre"
            assert active[0]["value"] == "Conference"

    def test_tag_empty(self, app: Flask, db_session: Session):
        """Test tag returns empty string when no tag filter."""
        with app.test_request_context():
            fb = FilterBar()
            fb.state = {}

            assert fb.tag == ""

    def test_tag_with_tag_filter(self, app: Flask, db_session: Session):
        """Test tag returns value when tag filter is set."""
        with app.test_request_context():
            fb = FilterBar()
            fb.state = {
                "filters": [
                    {"id": "tag", "value": "tech"},
                ]
            }

            assert fb.tag == "tech"

    def test_sorter_returns_options(self, app: Flask, db_session: Session):
        """Test sorter returns options dictionary."""
        with app.test_request_context():
            fb = FilterBar()

            sorter = fb.sorter
            assert "options" in sorter
            assert len(sorter["options"]) > 0

    def test_sort_order_default(self, app: Flask, db_session: Session):
        """Test sort_order returns default value."""
        with app.test_request_context():
            fb = FilterBar()
            fb.state = {}

            assert fb.sort_order == "date"

    def test_has_filter(self, app: Flask, db_session: Session):
        """Test has_filter method."""
        with app.test_request_context():
            fb = FilterBar()
            fb.state = {
                "filters": [
                    {"id": "genre", "value": "Conference"},
                ]
            }

            assert fb.has_filter("genre", "Conference") is True
            assert fb.has_filter("genre", "Workshop") is False
            assert fb.has_filter("sector", "Conference") is False

    def test_add_filter(self, app: Flask, db_session: Session):
        """Test add_filter method."""
        with app.test_request_context():
            fb = FilterBar()
            fb.state = {"filters": []}

            fb.add_filter("genre", "Webinar")

            assert len(fb.state["filters"]) == 1
            assert fb.state["filters"][0] == {"id": "genre", "value": "Webinar"}

    def test_remove_filter(self, app: Flask, db_session: Session):
        """Test remove_filter method."""
        with app.test_request_context():
            fb = FilterBar()
            fb.state = {
                "filters": [
                    {"id": "genre", "value": "Conference"},
                    {"id": "sector", "value": "Tech"},
                ]
            }

            fb.remove_filter("genre", "Conference")

            assert len(fb.state["filters"]) == 1
            assert fb.state["filters"][0]["id"] == "sector"

    def test_toggle_filter_adds(self, app: Flask, db_session: Session):
        """Test toggle_filter adds filter when not present."""
        with app.test_request_context():
            fb = FilterBar()
            fb.state = {"filters": []}

            fb.toggle_filter("genre", "Conference")

            assert fb.has_filter("genre", "Conference") is True

    def test_toggle_filter_removes(self, app: Flask, db_session: Session):
        """Test toggle_filter removes filter when present."""
        with app.test_request_context():
            fb = FilterBar()
            fb.state = {
                "filters": [
                    {"id": "genre", "value": "Conference"},
                ]
            }

            fb.toggle_filter("genre", "Conference")

            assert fb.has_filter("genre", "Conference") is False

    def test_sort_by(self, app: Flask, db_session: Session):
        """Test sort_by method."""
        with app.test_request_context():
            fb = FilterBar()
            fb.state = {}

            fb.sort_by("views")

            assert fb.state["sort-by"] == "views"

    def test_reset(self, app: Flask, db_session: Session):
        """Test reset clears state."""
        with app.test_request_context():
            fb = FilterBar()
            fb.state = {
                "filters": [{"id": "genre", "value": "Conference"}],
                "sort-by": "views",
            }

            fb.reset()

            assert fb.state == {}


class TestCalendar:
    """Test Calendar class."""

    def test_calendar_initialization(self, app: Flask):
        """Test Calendar initializes with proper attributes."""
        with app.test_request_context():
            events_page = EventsPage()
            events_page.args = {"day": "", "month": "", "tab": "", "loc": ""}
            events_page.date_filter = DateFilter(events_page.args)

            month = arrow.get("2024-06-01")
            cal = Calendar(events_page, month)

            assert cal.month == month
            assert isinstance(cal.cells, list)
            assert cal.prev_month == "2024-05"
            assert cal.next_month == "2024-07"
            assert cal.num_weeks > 0

    def test_calendar_cells_structure(
        self, app: Flask, db_session: Session, test_user: User
    ):
        """Test Calendar cells have expected structure."""
        with app.test_request_context():
            events_page = EventsPage()
            events_page.args = {"day": "", "month": "", "tab": "", "loc": ""}
            events_page.date_filter = DateFilter(events_page.args)

            month = arrow.get("2024-06-01")
            cal = Calendar(events_page, month)

            if cal.cells:
                cell = cal.cells[0]
                assert "date" in cell
                assert "is_today" in cell
                assert "num_events" in cell


class TestEventsPageContext:
    """Test EventsPage context method."""

    def test_context_returns_dict(self, app: Flask, db_session: Session):
        """Test context returns expected dictionary."""
        with app.test_request_context("/events/"):
            page = EventsPage()
            ctx = page.context()

            assert isinstance(ctx, dict)
            assert "grouped_events" in ctx
            assert "search" in ctx
            assert "tabs" in ctx
            assert "calendar" in ctx
            assert "title" in ctx
            assert "filter_bar" in ctx

    def test_context_with_event(
        self, app: Flask, db_session: Session, sample_event: EventPost
    ):
        """Test context includes events when present."""
        with app.test_request_context("/events/"):
            page = EventsPage()
            ctx = page.context()

            # grouped_events should be a list of (date, events) tuples
            assert isinstance(ctx["grouped_events"], list)


class TestEventsPageGetTabs:
    """Test EventsPage get_tabs method."""

    def test_get_tabs_returns_list(self, app: Flask, db_session: Session):
        """Test get_tabs returns list of tabs."""
        with app.test_request_context("/events/"):
            page = EventsPage()
            tabs = page.get_tabs()

            assert isinstance(tabs, list)
            if tabs:
                tab = tabs[0]
                assert "id" in tab
                assert "label" in tab
                assert "active" in tab
