# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Unit tests for security/decorators.py."""

from __future__ import annotations

from app.modules.security.decorators import requires_role


class TestRequiresRole:
    """Test suite for requires_role decorator."""

    def test_requires_role_returns_callable(self):
        """Test that requires_role returns a callable decorator."""
        decorator = requires_role("admin")
        assert callable(decorator)

    def test_requires_role_accepts_role_string(self):
        """Test that requires_role accepts role as a string."""
        decorator = requires_role("editor")
        assert callable(decorator)

    def test_requires_role_decorates_function(self):
        """Test that requires_role can decorate a function."""

        @requires_role("viewer")
        def protected_view():
            return "success"

        # The decorated function should still be callable
        assert callable(protected_view)

    def test_requires_role_preserves_function_name(self):
        """Test that requires_role preserves the decorated function's name."""

        @requires_role("admin")
        def my_protected_function():
            pass

        # Flask-Security should preserve function metadata
        assert "my_protected_function" in str(my_protected_function)
