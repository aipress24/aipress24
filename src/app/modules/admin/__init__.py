# Copyright (c) 2021-2024 - Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from typing import cast

from flask import Blueprint
from flask_login import current_user
from werkzeug.exceptions import Unauthorized

from app.models.auth import User
from app.services.roles import has_role

blueprint = Blueprint(
    "admin", __name__, url_prefix="/admin", template_folder="templates"
)
route = blueprint.route


@blueprint.before_request
def check_admin():
    user = cast(User, current_user)
    if not has_role(user, "ADMIN"):
        raise Unauthorized
