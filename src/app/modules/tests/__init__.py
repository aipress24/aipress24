# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Diagnostic test endpoints.

Lightweight routes used to isolate where a problem lies — e.g. whether
a large-file upload is rejected by nginx / the reverse proxy before
reaching Flask, or by Flask itself. Not gated by any role, but requires
an authenticated session to keep the endpoints off the open internet.
"""

from __future__ import annotations

from typing import cast

from flask import Blueprint
from flask_login import current_user
from werkzeug.exceptions import Unauthorized

from app.models.auth import User

blueprint = Blueprint("tests", __name__, url_prefix="/tests")


@blueprint.before_request
def check_auth() -> None:
    user = cast("User", current_user)
    if user.is_anonymous:
        raise Unauthorized


from . import views  # noqa: E402, F401
