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

from flask import Blueprint, Response, request
from flask_login import current_user

from app.models.auth import User

# Client-side cache directive applied to every /media response.
# `private` forbids shared caches (content isn't truly public).
# `immutable` + one-year max-age tells the browser the bytes never change
# at this URL (the URL IS the content hash), so no revalidation is needed.
_MEDIA_CACHE_CONTROL = "private, max-age=31536000, immutable"

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


@blueprint.record_once
def _register_cache_control_override(setup_state) -> None:
    """Ensure our Cache-Control wins over Flask-Security's default.

    Flask-Security registers a global `after_app_request` hook that
    appends `private=True, no-store=True` to every response via dict-
    style assignment (which Werkzeug serialises with the malformed
    `=True` form and which defeats caching on immutable static assets).

    Flask runs after-request handlers in reverse registration order, so
    whichever handler is registered LAST runs FIRST — meaning the
    earliest-registered hook has the final word on the response. By the
    time this blueprint registers, Flask-Security's hook is already at
    the head of the list, so we insert ours at position 0 (pushing
    Flask-Security's to position 1). Reverse traversal then runs
    Flask-Security first, ours last — our value wins.
    """
    app = setup_state.app
    app.after_request_funcs.setdefault(None, []).insert(0, _fix_cache_control)


def _fix_cache_control(response: Response) -> Response:
    if request.blueprint == "media" and response.status_code == 200:
        response.headers["Cache-Control"] = _MEDIA_CACHE_CONTROL
    return response


from . import views  # noqa: E402, F401
