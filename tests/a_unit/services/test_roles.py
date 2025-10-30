# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Tests for services/roles module."""

from __future__ import annotations

from flask_sqlalchemy import SQLAlchemy
from svcs.flask import container

from app.enums import RoleEnum
from app.models.auth import Role, User
from app.models.repositories import RoleRepository
from app.services.roles import add_role, generate_roles_map, has_role


class TestGenerateRolesMap:
    """Test suite for generate_roles_map function."""

    def test_generate_roles_map(self, db: SQLAlchemy) -> None:
        """Test generating roles map."""
        # Create some roles
        role1 = Role(name="admin")
        role2 = Role(name="moderator")
        role3 = Role(name="user")
        db.session.add_all([role1, role2, role3])
        db.session.flush()

        roles_map = generate_roles_map()

        assert isinstance(roles_map, dict)
        assert "admin" in roles_map
        assert "moderator" in roles_map
        assert "user" in roles_map
        assert roles_map["admin"].name == "admin"

    def test_generate_roles_map_empty(self, db: SQLAlchemy) -> None:
        """Test generating roles map when no roles exist."""
        # Clear any existing roles
        role_repo = container.get(RoleRepository)
        for role in role_repo.list():
            db.session.delete(role)
        db.session.flush()

        roles_map = generate_roles_map()
        assert isinstance(roles_map, dict)


class TestAddRole:
    """Test suite for add_role function."""

    def test_add_role_with_string(self, db: SQLAlchemy) -> None:
        """Test adding a role using string name."""
        user = User(email="test@example.com")
        role = Role(name="editor")
        db.session.add_all([user, role])
        db.session.flush()

        add_role(user, "editor")

        assert user.has_role("editor")

    def test_add_role_with_role_enum(self, db: SQLAlchemy) -> None:
        """Test adding a role using RoleEnum."""
        user = User(email="test@example.com")
        # Create role with name matching enum
        role = Role(name=RoleEnum.ADMIN.name)
        db.session.add_all([user, role])
        db.session.flush()

        add_role(user, RoleEnum.ADMIN)

        assert user.has_role(RoleEnum.ADMIN.name)

    def test_add_role_with_role_object(self, db: SQLAlchemy) -> None:
        """Test adding a role using Role object."""
        user = User(email="test@example.com")
        role = Role(name="contributor")
        db.session.add_all([user, role])
        db.session.flush()

        add_role(user, role)

        assert user.has_role("contributor")

    def test_add_role_with_precomputed_map(self, db: SQLAlchemy) -> None:
        """Test adding a role with pre-computed roles_map for performance."""
        user = User(email="test@example.com")
        role = Role(name="viewer")
        db.session.add_all([user, role])
        db.session.flush()

        # Pre-compute the roles map
        roles_map = generate_roles_map()

        # Add role using the pre-computed map
        add_role(user, "viewer", roles_map=roles_map)

        assert user.has_role("viewer")


class TestHasRole:
    """Test suite for has_role function."""

    def test_has_role_with_string(self, db: SQLAlchemy) -> None:
        """Test checking role with string."""
        user = User(email="test@example.com")
        role = Role(name="admin")
        user.add_role(role)
        db.session.add_all([user, role])
        db.session.flush()

        assert has_role(user, "admin") is True
        assert has_role(user, "moderator") is False

    def test_has_role_with_role_enum(self, db: SQLAlchemy) -> None:
        """Test checking role with RoleEnum."""
        user = User(email="test@example.com")
        role = Role(name=RoleEnum.GUEST.name)
        user.add_role(role)
        db.session.add_all([user, role])
        db.session.flush()

        assert has_role(user, RoleEnum.GUEST) is True

    def test_has_role_with_role_object(self, db: SQLAlchemy) -> None:
        """Test checking role with Role object."""
        user = User(email="test@example.com")
        role = Role(name="editor")
        user.add_role(role)
        db.session.add_all([user, role])
        db.session.flush()

        assert has_role(user, role) is True

    def test_has_role_with_list(self, db: SQLAlchemy) -> None:
        """Test checking if user has any role from a list."""
        user = User(email="test@example.com")
        admin_role = Role(name="admin")
        user.add_role(admin_role)
        db.session.add_all([user, admin_role])
        db.session.flush()

        # User has admin, checking for admin or moderator
        assert has_role(user, ["admin", "moderator"]) is True

        # User doesn't have any of these
        assert has_role(user, ["viewer", "guest"]) is False

    def test_has_role_with_set(self, db: SQLAlchemy) -> None:
        """Test checking if user has any role from a set."""
        user = User(email="test@example.com")
        editor_role = Role(name="editor")
        user.add_role(editor_role)
        db.session.add_all([user, editor_role])
        db.session.flush()

        assert has_role(user, {"editor", "admin"}) is True
        assert has_role(user, {"viewer", "guest"}) is False

    def test_has_role_anonymous_user(self, db: SQLAlchemy) -> None:
        """Test that anonymous users always return False."""

        # Create an anonymous user mock
        class AnonymousUser:
            is_anonymous = True

        user = AnonymousUser()

        assert has_role(user, "admin") is False  # type: ignore
        assert has_role(user, ["admin", "moderator"]) is False  # type: ignore

    def test_has_role_unsupported_type(self, db: SQLAlchemy) -> None:
        """Test that unsupported role types raise ValueError."""
        user = User(email="test@example.com")
        db.session.add(user)
        db.session.flush()

        import pytest

        with pytest.raises(ValueError, match="Match failed"):
            has_role(user, 123)  # type: ignore

        with pytest.raises(ValueError, match="Match failed"):
            has_role(user, {"role": "admin"})  # type: ignore
