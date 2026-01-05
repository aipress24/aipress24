"""Admin module with administrative functionality."""
# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from typing import cast

from flask import Blueprint
from flask_login import current_user
from werkzeug.exceptions import Unauthorized

from app.enums import RoleEnum
from app.flask.lib.nav import configure_nav
from app.models.auth import User
from app.services.roles import has_role

blueprint = Blueprint(
    "admin", __name__, url_prefix="/admin", template_folder="templates"
)
# Navigation configuration - ACL here is inherited by all child routes
configure_nav(
    blueprint,
    label="Admin",
    icon="cog",
    order=100,
    acl=[("Allow", RoleEnum.ADMIN, "view")],
)
route = blueprint.route


@blueprint.before_request
def check_admin() -> None:
    """Check if current user has admin role before processing requests.

    Raises:
        Unauthorized: If user does not have ADMIN role.
    """
    user = cast("User", current_user)
    if not has_role(user, "ADMIN"):
        raise Unauthorized


def register_views() -> None:
    """Register views with the blueprint.

    This function is called during app initialization to avoid
    circular imports that occur when views are imported at module load time.
    """
    from . import views  # noqa: F401
