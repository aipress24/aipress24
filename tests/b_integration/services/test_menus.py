# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Tests for services/menus module."""

from __future__ import annotations

from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from svcs.flask import container

from app.models.auth import User
from app.services.menus import MenuService


def test_menu_service_getitem(app: Flask, app_context, db: SQLAlchemy) -> None:
    """Test MenuService __getitem__ method."""
    menu_service = container.get(MenuService)

    # Create a user with some roles for testing
    user = User(email="test@example.com")
    db.session.add(user)
    db.session.flush()

    # Get a standard menu - this should work
    with app.test_request_context("/"):
        from flask import g

        g.user = user
        menu = menu_service["main"]
        assert isinstance(menu, list)


def test_menu_service_update_dict(app: Flask, app_context) -> None:
    """Test MenuService update method with dict."""
    menu_service = container.get(MenuService)

    custom_menu = [{"label": "Custom", "endpoint": "/custom"}]
    menu_service.update({"custom": custom_menu})

    with app.test_request_context("/"):
        result = menu_service["custom"]
        assert isinstance(result, list)


def test_menu_service_update_kwargs(app: Flask, app_context) -> None:
    """Test MenuService update method with kwargs."""
    menu_service = container.get(MenuService)

    custom_menu = [{"label": "Test", "endpoint": "/test"}]
    menu_service.update(test_menu=custom_menu)

    with app.test_request_context("/"):
        result = menu_service["test_menu"]
        assert isinstance(result, list)


def test_make_menu_entry_with_hash_endpoint(
    app: Flask, app_context, db: SQLAlchemy
) -> None:
    """Test _make_menu_entry with # endpoint."""
    from app.services.menus import _make_menu_entry

    user = User(email="test@example.com")
    db.session.add(user)
    db.session.flush()

    with app.test_request_context("/"):
        from flask import g

        g.user = user

        spec = {"label": "Placeholder", "endpoint": "#"}
        entry = _make_menu_entry(spec)

        assert entry is not None
        assert entry["url"] == "#"
        assert entry["label"] == "Placeholder"


def test_make_menu_entry_with_slash_endpoint(
    app: Flask, app_context, db: SQLAlchemy
) -> None:
    """Test _make_menu_entry with / endpoint."""
    from app.services.menus import _make_menu_entry

    user = User(email="test@example.com")
    db.session.add(user)
    db.session.flush()

    with app.test_request_context("/test"):
        from flask import g

        g.user = user

        spec = {"label": "Direct", "endpoint": "/direct"}
        entry = _make_menu_entry(spec)

        assert entry is not None
        assert entry["url"] == "/direct"
        assert entry["active"] is False  # path is /test, not /direct


def test_make_menu_entry_with_tooltip(app: Flask, app_context, db: SQLAlchemy) -> None:
    """Test _make_menu_entry includes tooltip."""
    from app.services.menus import _make_menu_entry

    user = User(email="test@example.com")
    db.session.add(user)
    db.session.flush()

    with app.test_request_context("/"):
        from flask import g

        g.user = user

        spec = {"label": "Help", "endpoint": "#", "tooltip": "Get help"}
        entry = _make_menu_entry(spec)

        assert entry is not None
        assert entry["tooltip"] == "Get help"


def test_make_menu_active_deduplication(
    app: Flask, app_context, db: SQLAlchemy
) -> None:
    """Test make_menu deduplicates active entries."""
    from app.services.menus import make_menu

    user = User(email="test@example.com")
    db.session.add(user)
    db.session.flush()

    with app.test_request_context("/test/sub"):
        from flask import g

        g.user = user

        specs = [
            {"label": "Test", "endpoint": "/test"},
            {"label": "Test Sub", "endpoint": "/test/sub"},
            {"label": "Other", "endpoint": "/other"},
        ]
        menu = make_menu(specs)

        # Only the most specific active entry should be marked as active
        active_entries = [e for e in menu if e.get("active")]
        assert len(active_entries) == 1
        assert active_entries[0]["endpoint"] == "/test/sub"


def test_make_menu_entry_with_role_filtering(
    app: Flask, app_context, db: SQLAlchemy
) -> None:
    """Test _make_menu_entry filters by role."""
    from app.models.auth import Role
    from app.services.menus import _make_menu_entry

    # Create user with role
    user = User(email="test@example.com")
    admin_role = Role(name="admin")
    user.roles.append(admin_role)
    db.session.add_all([user, admin_role])
    db.session.flush()

    with app.test_request_context("/"):
        from flask import g

        g.user = user

        # Entry requiring admin role - should be visible
        spec1 = {"label": "Admin", "endpoint": "#", "roles": {"admin"}}
        entry1 = _make_menu_entry(spec1)
        assert entry1 is not None

        # Entry requiring different role - should be None
        spec2 = {"label": "Moderator", "endpoint": "#", "roles": {"moderator"}}
        entry2 = _make_menu_entry(spec2)
        assert entry2 is None
