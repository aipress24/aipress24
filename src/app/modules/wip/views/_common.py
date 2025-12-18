# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Common utilities for wip views."""

from __future__ import annotations

from flask import g, redirect, url_for


def check_auth():
    """Redirect unauthenticated users to login."""
    if not g.user.is_authenticated:
        return redirect(url_for("security.login"))
    return None


def get_secondary_menu(current_name: str):
    """Get secondary menu for wip pages."""
    # Lazy import to avoid circular import
    from ..menu import make_menu

    return make_menu(current_name)
