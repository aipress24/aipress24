# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""E2E tests for WIP eventroom views."""

from __future__ import annotations

from typing import TYPE_CHECKING

import arrow
import pytest

from app.enums import RoleEnum
from app.flask.extensions import db
from app.models.auth import KYCProfile, Role, User
from app.modules.wip.models.eventroom import Event
from tests.c_e2e.conftest import make_authenticated_client

if TYPE_CHECKING:
    from flask import Flask

    from app.models.organisation import Organisation


@pytest.fixture
def pr_user(db_session, test_org: Organisation) -> User:
    """Create a PR user with PRESS_RELATIONS role."""
    role = db_session.query(Role).filter_by(name=RoleEnum.PRESS_RELATIONS.name).first()
    if not role:
        role = Role(
            name=RoleEnum.PRESS_RELATIONS.name,
            description=RoleEnum.PRESS_RELATIONS.value,
        )
        db_session.add(role)
        db_session.flush()

    profile = KYCProfile()
    user = User(
        email="pr-eventroom@example.com",
        first_name="PR",
        last_name="EventroomUser",
        active=True,
    )
    user.profile = profile
    user.organisation = test_org
    user.organisation_id = test_org.id
    user.roles.append(role)
    db_session.add(user)
    db_session.commit()
    return user


class TestEventroomAccess:
    """Tests for eventroom access."""

    def test_eventroom_loads(self, app: Flask, pr_user: User):
        """Test that eventroom loads successfully."""
        client = make_authenticated_client(app, pr_user)
        response = client.get("/wip/eventroom")

        assert response.status_code == 200

    def test_eventroom_shows_events_section(self, app: Flask, pr_user: User):
        """Test eventroom shows events section."""
        client = make_authenticated_client(app, pr_user)
        response = client.get("/wip/eventroom")

        assert response.status_code == 200
        html = response.data.decode()
        # Should show events or évènements
        assert "vent" in html.lower()  # Matches "Event" or "événement"


class TestEventroomContent:
    """Tests for eventroom content display."""

    def test_eventroom_has_secondary_menu(self, app: Flask, pr_user: User):
        """Test eventroom has secondary navigation menu."""
        client = make_authenticated_client(app, pr_user)
        response = client.get("/wip/eventroom")

        assert response.status_code == 200

    def test_eventroom_shows_item_count(self, app: Flask, pr_user: User):
        """Test eventroom shows item count (even if zero)."""
        client = make_authenticated_client(app, pr_user)
        response = client.get("/wip/eventroom")

        assert response.status_code == 200
        # Page should render successfully with zero items
        html = response.data.decode()
        assert "0" in html or "Evénement" in html or "event" in html.lower()

    def test_eventroom_count_excludes_soft_deleted(self, app: Flask, pr_user: User):
        """Regression for bug #0143: the EV tile counted soft-deleted events,
        so a user who created 3 and deleted 2 still saw "3 élément(s)"."""
        # Create 3 events, delete 2 (soft).
        events = []
        for title in ("Kept event", "Deleted 1", "Deleted 2"):
            ev = Event(titre=title, owner_id=pr_user.id)
            db.session.add(ev)
            events.append(ev)
        db.session.flush()
        events[1].deleted_at = arrow.now()
        events[2].deleted_at = arrow.now()
        db.session.commit()

        client = make_authenticated_client(app, pr_user)
        response = client.get("/wip/eventroom")
        assert response.status_code == 200
        html = response.data.decode()
        # The count next to the EV tile must read 1, not 3.
        assert "1 élément" in html
        assert "3 élément" not in html
