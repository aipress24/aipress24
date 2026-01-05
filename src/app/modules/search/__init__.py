# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from typing import cast

from flask import Blueprint
from flask_login import current_user
from werkzeug.exceptions import Unauthorized

from app.flask.lib.nav import configure_nav
from app.models.auth import User

blueprint = Blueprint(
    "search", __name__, url_prefix="/search", template_folder="templates"
)
configure_nav(blueprint, label="Rechercher", icon="search", order=10)
route = blueprint.route


@blueprint.before_request
def check_auth() -> None:
    user = cast("User", current_user)
    if user.is_anonymous:
        raise Unauthorized


def register_views() -> None:
    """Register views with the blueprint.

    This function is called during app initialization to avoid
    circular imports that occur when views are imported at module load time.
    """
    from . import views  # noqa: F401
