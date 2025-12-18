# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from pathlib import Path
from typing import cast

from flask import Blueprint, current_app, send_from_directory
from flask_login import current_user
from werkzeug.exceptions import Unauthorized

from app.models.auth import User

blueprint = Blueprint(
    "preferences", __name__, url_prefix="/preferences", template_folder="templates"
)
route = blueprint.route

# Navigation configuration for this section
blueprint.nav = {
    "label": "Préférences",
    "icon": "cog",
    "order": 9,  # Near the end
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


# Import views to register routes
from . import views  # noqa: E402, F401
