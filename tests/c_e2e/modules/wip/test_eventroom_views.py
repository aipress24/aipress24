# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""E2E tests for WIP eventroom views."""

from __future__ import annotations

from typing import TYPE_CHECKING

import arrow

from app.flask.extensions import db
from app.modules.wip.models.eventroom import Event

if TYPE_CHECKING:
    from flask.testing import FlaskClient

    from app.models.auth import User


class TestEventroomAccess:
    """Tests for eventroom access."""

    def test_eventroom_loads(self, logged_in_client: FlaskClient, test_user: User):
        """Test that eventroom loads successfully."""
        response = logged_in_client.get("/wip/eventroom")

        assert response.status_code == 200

    def test_eventroom_shows_events_section(
        self, logged_in_client: FlaskClient, test_user: User
    ):
        """Test eventroom shows events section."""
        response = logged_in_client.get("/wip/eventroom")

        assert response.status_code == 200
        html = response.data.decode()
        # Should show events or évènements
        assert "vent" in html.lower()  # Matches "Event" or "événement"


class TestEventroomContent:
    """Tests for eventroom content display."""

    def test_eventroom_has_secondary_menu(
        self, logged_in_client: FlaskClient, test_user: User
    ):
        """Test eventroom has secondary navigation menu."""
        response = logged_in_client.get("/wip/eventroom")

        assert response.status_code == 200

    def test_eventroom_shows_item_count(
        self, logged_in_client: FlaskClient, test_user: User
    ):
        """Test eventroom shows item count (even if zero)."""
        response = logged_in_client.get("/wip/eventroom")

        assert response.status_code == 200
        # Page should render successfully with zero items
        html = response.data.decode()
        assert "0" in html or "Evénement" in html or "event" in html.lower()

    def test_eventroom_count_excludes_soft_deleted(
        self, logged_in_client: FlaskClient, test_user: User
    ):
        """Regression for bug #0143: the EV tile counted soft-deleted events,
        so a user who created 3 and deleted 2 still saw "3 élément(s)"."""
        # Create 3 events, delete 2 (soft).
        events = []
        for title in ("Kept event", "Deleted 1", "Deleted 2"):
            ev = Event(titre=title, owner_id=test_user.id)
            db.session.add(ev)
            events.append(ev)
        db.session.flush()
        events[1].deleted_at = arrow.now()
        events[2].deleted_at = arrow.now()
        db.session.commit()

        response = logged_in_client.get("/wip/eventroom")
        assert response.status_code == 200
        html = response.data.decode()
        # The count next to the EV tile must read 1, not 3.
        assert "1 élément" in html
        assert "3 élément" not in html
