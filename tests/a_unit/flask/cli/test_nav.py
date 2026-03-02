# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Unit tests for flask/cli/nav.py."""

from __future__ import annotations

import click
import pytest

from app.enums import RoleEnum
from app.flask.cli.nav import _create_mock_user_with_roles, _resolve_filter_user


class TestCreateMockUserWithRoles:
    """Test _create_mock_user_with_roles function."""

    def test_creates_user_with_single_role(self, app):
        """Creates mock user with one role."""
        with app.app_context():
            user = _create_mock_user_with_roles(["PRESS_MEDIA"])

            assert user.is_anonymous is False
            assert len(user.roles) == 1
            assert user.roles[0].name == "PRESS_MEDIA"

    def test_creates_user_with_multiple_roles(self, app):
        """Creates mock user with multiple roles."""
        with app.app_context():
            user = _create_mock_user_with_roles(["PRESS_MEDIA", "ACADEMIC"])

            assert len(user.roles) == 2
            role_names = {r.name for r in user.roles}
            assert role_names == {"PRESS_MEDIA", "ACADEMIC"}

    def test_normalizes_role_names(self, app):
        """Normalizes role names to uppercase."""
        with app.app_context():
            user = _create_mock_user_with_roles(["press_media"])

            assert user.roles[0].name == "PRESS_MEDIA"

    def test_raises_for_unknown_role(self, app):
        """Raises ClickException for unknown role."""
        with (
            app.app_context(),
            pytest.raises(click.ClickException, match="Unknown role"),
        ):
            _create_mock_user_with_roles(["INVALID_ROLE"])


class TestMockUserHasRole:
    """Test MockUser.has_role method."""

    def test_has_role_with_enum(self, app):
        """Returns True when user has role (enum check)."""
        with app.app_context():
            user = _create_mock_user_with_roles(["PRESS_MEDIA"])

            assert user.has_role(RoleEnum.PRESS_MEDIA) is True
            assert user.has_role(RoleEnum.ACADEMIC) is False

    def test_has_role_with_string(self, app):
        """Returns True when user has role (string check)."""
        with app.app_context():
            user = _create_mock_user_with_roles(["PRESS_MEDIA"])

            assert user.has_role("PRESS_MEDIA") is True
            assert user.has_role("ACADEMIC") is False


class TestResolveFilterUser:
    """Test _resolve_filter_user function."""

    def test_raises_when_both_email_and_roles_provided(self, app):
        """Raises when both --email and --roles are provided."""
        with (
            app.app_context(),
            pytest.raises(click.ClickException, match="Cannot use both"),
        ):
            _resolve_filter_user(email="test@example.com", roles="PRESS_MEDIA")

    def test_returns_none_when_no_filters(self, app):
        """Returns (None, None) when no filters provided."""
        with app.app_context():
            user, description = _resolve_filter_user(email=None, roles=None)

            assert user is None
            assert description is None

    def test_creates_mock_user_from_roles(self, app):
        """Creates mock user when --roles is provided."""
        with app.app_context():
            user, description = _resolve_filter_user(
                email=None, roles="PRESS_MEDIA,ACADEMIC"
            )

            assert user is not None
            assert "roles:" in description
            assert len(user.roles) == 2
