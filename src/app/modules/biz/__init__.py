"""Business module for business-related functionality."""
# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from typing import cast

from flask import Blueprint
from flask_login import current_user
from werkzeug.exceptions import Unauthorized

from app.models.auth import User

blueprint = Blueprint("biz", __name__, url_prefix="/biz", template_folder="templates")
route = blueprint.route

# Navigation configuration for convention-driven nav
blueprint.nav = {
    "label": "Marketplace",
    "icon": "shopping-cart",
    "order": 40,
}


@blueprint.before_request
def check_auth() -> None:
    """Check if user is authenticated before processing business requests.

    Raises:
        Unauthorized: If user is anonymous/not authenticated.
    """
    user = cast("User", current_user)
    if user.is_anonymous:
        raise Unauthorized


# Import views to register routes
from . import views  # noqa: E402, F401
