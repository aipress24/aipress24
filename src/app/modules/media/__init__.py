# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Content-addressed media serving.

Serves uploaded files under stable, content-hash URLs so they can be
cached aggressively (immutable bytes) and shared across models without
per-model authz gates. Requires an authenticated session: the SHA256 is
unguessable but not a substitute for auth, since nothing served here is
truly public (KYC docs, justificatifs, drafts all live on the same
backend).
"""

from __future__ import annotations

from typing import cast

from flask import Blueprint, Response
from flask_login import current_user

from app.models.auth import User

blueprint = Blueprint("media", __name__, url_prefix="/media")


@blueprint.before_request
def check_auth() -> Response | None:
    # Return a plain 401 rather than letting Flask-Security redirect to
    # the login page — these URLs sit inside <img> tags, where an HTML
    # redirect would just paint a broken image. 401 lets the browser
    # show its native broken-image icon and keeps the response cheap.
    user = cast("User", current_user)
    if user.is_anonymous:
        return Response(status=401)
    return None


from . import views  # noqa: E402, F401
