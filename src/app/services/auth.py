"""Authentication service for user management."""
# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from flask import g
from flask_super.decorators import service


@service
class AuthService:
    """Service for authentication-related operations."""

    def get_user(self):
        """Get the current user from Flask's global context.

        Returns:
            User: Current user object.
        """
        return g.user
