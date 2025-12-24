# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from pathlib import Path
from typing import cast

from flask import Blueprint, current_app, send_from_directory
from flask_login import current_user
from werkzeug.exceptions import Unauthorized

from app.enums import RoleEnum
from app.models.auth import User

blueprint = Blueprint(
    "preferences", __name__, url_prefix="/preferences", template_folder="templates"
)
route = blueprint.route

# Navigation configuration - SELF ACL inherited by all child routes
# (SELF means "visible to authenticated users, ownership checked in view")
blueprint.nav = {
    "label": "Préférences",
    "icon": "cog",
    "order": 9,  # Near the end
    "acl": [("Allow", RoleEnum.SELF, "view")],
}


@blueprint.route("/images/<path:filename>")
def images_page(filename):
    images_dir = Path(current_app.instance_path) / "images"
    return send_from_directory(images_dir, filename)


@blueprint.before_request
def check_auth() -> None:
    user = cast("User", current_user)
    if user.is_anonymous:
        raise Unauthorized


@blueprint.context_processor
def inject_preferences_menu() -> dict:
    """Inject preferences menu into template context."""
    from flask import request

    from app.modules.preferences.menu import make_menu

    # Get current page name from endpoint
    endpoint = request.endpoint or ""
    name = endpoint.split(".")[-1] if "." in endpoint else endpoint
    return {"menus": {"secondary": make_menu(name)}}


def register_views() -> None:
    """Register views with the blueprint.

    This function is called during app initialization to avoid
    circular imports that occur when views are imported at module load time.
    """
    from . import views  # noqa: F401
