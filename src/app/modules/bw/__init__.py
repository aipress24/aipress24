"""Business Wall registration module."""
# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

# from flask import Blueprint
# from flask_login import current_user
# from werkzeug.exceptions import Unauthorized
from app.flask.lib.nav import configure_nav

# from app.models.auth import User
# Register blueprints
from .bw_activation import bp as bw_activation_bp

configure_nav(bw_activation_bp, label="Activation BW", icon="users", order=20)
route = bw_activation_bp.route


def register_views() -> None:
    """Register views with the blueprint.

    This function is called during app initialization to avoid
    circular imports that occur when views are imported at module load time.
    """
    # from . import views  # noqa: F401
