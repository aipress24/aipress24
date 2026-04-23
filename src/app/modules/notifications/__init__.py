# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""In-app notifications UI routes.

The notification model and service live under
`app.services.notifications`. This module only exposes the user-facing
actions (`mark as read`, `mark all as read`) and the bell-dropdown
wiring. Requires an authenticated session.
"""

from __future__ import annotations

from typing import cast

from flask import Blueprint
from flask_login import current_user
from werkzeug.exceptions import Unauthorized

from app.models.auth import User

blueprint = Blueprint("notifications", __name__, url_prefix="/notifications")


@blueprint.before_request
def check_auth() -> None:
    user = cast("User", current_user)
    if user.is_anonymous:
        raise Unauthorized


from . import views  # noqa: E402, F401
