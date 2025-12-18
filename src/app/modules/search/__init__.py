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
    "search", __name__, url_prefix="/search", template_folder="templates"
)
route = blueprint.route

# Navigation configuration for this section
blueprint.nav = {
    "label": "Rechercher",
    "icon": "search",
    "order": 10,  # Usually last in nav
}


@blueprint.before_request
def check_auth() -> None:
    user = cast("User", current_user)
    if user.is_anonymous:
        raise Unauthorized


# Import views to register routes
from . import views  # noqa: E402, F401
