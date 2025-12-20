"""Social work module for collaborative workspace functionality."""
# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from typing import cast

from flask import Blueprint
from flask_login import current_user
from werkzeug.exceptions import Unauthorized

from app.models.auth import User

blueprint = Blueprint(
    "swork", __name__, url_prefix="/swork", template_folder="templates"
)
route = blueprint.route

# Navigation configuration for convention-driven nav
blueprint.nav = {
    "label": "Social",
    "icon": "users",
    "order": 20,
}


@blueprint.before_request
def check_auth() -> None:
    """Check if user is authenticated before processing social work requests.

    Raises:
        Unauthorized: If user is anonymous/not authenticated.
    """
    user = cast("User", current_user)
    if user.is_anonymous:
        raise Unauthorized


@blueprint.context_processor
def inject_swork_menu() -> dict:
    """Inject swork menu into template context."""
    from app.modules.swork.settings import SWORK_MENU
    from app.services.menus import make_menu

    menu = make_menu(SWORK_MENU)
    return {"nav_secondary_menu": menu}


def register_views() -> None:
    """Register views with the blueprint.

    This function is called during app initialization to avoid
    circular imports that occur when views are imported at module load time.
    """
    from . import views  # noqa: F401
