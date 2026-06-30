# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Unit tests for wip views common utilities."""

from __future__ import annotations

import arrow
from flask import g
from flask_security.core import AnonymousUser

from app.models.auth import User
from app.modules.wip.models.eventroom import Event
from app.modules.wip.views._common import (
    check_auth,
    count_owned_non_deleted,
    get_secondary_menu,
)


class TestCheckAuth:
    """Tests for the check_auth function."""

    def test_check_auth_authenticated(self, app):
        """check_auth returns None for an authenticated user."""
        with app.test_request_context():
            g.user = User(email="auth@example.com", active=True)
            assert check_auth() is None

    def test_check_auth_not_authenticated(self, app):
        """check_auth redirects an anonymous visitor to login."""
        with app.test_request_context():
            g.user = AnonymousUser()
            result = check_auth()
            assert result is not None
            assert result.status_code == 302


class TestCountOwnedNonDeleted:
    """Regression for bug #0143 (and its sibling defects in com'room and
    newsroom): the room tiles used to count soft-deleted rows."""

    def test_excludes_soft_deleted(self, app, db_session):
        user = User(email="counter@example.com", active=True)
        db_session.add(user)
        db_session.flush()

        kept = Event(titre="Kept", owner_id=user.id)
        deleted = Event(titre="Gone", owner_id=user.id)
        db_session.add_all([kept, deleted])
        db_session.flush()
        deleted.deleted_at = arrow.now()
        db_session.flush()

        with app.test_request_context():
            g.user = user
            count = count_owned_non_deleted(Event)
        assert count == 1

    def test_zero_when_no_rows(self, app, db_session):
        user = User(email="empty@example.com", active=True)
        db_session.add(user)
        db_session.flush()

        with app.test_request_context():
            g.user = user
            count = count_owned_non_deleted(Event)
        assert count == 0


class TestGetSecondaryMenu:
    """Tests for the get_secondary_menu function."""

    def test_get_secondary_menu(self, app):
        """get_secondary_menu returns a list of menu items."""
        with app.test_request_context():
            g.user = User(email="menu@example.com", active=True)
            menu = get_secondary_menu("dashboard")
            assert isinstance(menu, list)
