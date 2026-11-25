# Copyright (c) 2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only
"""Web pages to manage API keys: one's own, and everybody's for admins.

They are added to the preferences and admin blueprints, which bring their
access checks and menus, rather than defined there: those modules may not
depend on the API.
"""

from __future__ import annotations

from typing import ClassVar, cast

import sqlalchemy as sa
from flask import Response, flash, g, make_response, redirect, render_template, request
from flask.views import MethodView
from flask_security.decorators import auth_required
from flask_security.utils import config_value
from loguru import logger
from werkzeug import Response as WerkzeugResponse
from werkzeug.exceptions import NotFound

from app.flask.extensions import db
from app.flask.lib.nav import nav
from app.flask.routing import url_for
from app.models.auth import User
from app.modules.admin import blueprint as admin_blueprint
from app.modules.preferences import blueprint as preferences_blueprint

from .models import ApiToken
from .tokens import (
    LIFETIMES,
    MAX_NAME_LENGTH,
    MEMBER_SCOPES,
    TokenRefusedError,
    active_tokens,
    issue_member_token,
    revoke_token,
)


class ApiKeysView(MethodView):
    """Clés d'API."""

    # A key outlives the session that creates it: ask for the password again
    # when the login is not recent.
    decorators: ClassVar[list] = [
        auth_required("session", within=lambda: config_value("FRESHNESS"))
    ]

    def get(self) -> Response:
        return _render_keys()

    def post(self) -> Response:
        user = cast("User", g.user)
        try:
            secret = issue_member_token(
                db.session,
                user,
                request.form.get("name", ""),
                request.form.getlist("scopes"),
                request.form.get("days", type=int),
            )
        except TokenRefusedError as exc:
            return _render_keys(error=str(exc))
        db.session.commit()
        logger.info("API key issued by user {}", user.id)
        return _render_keys(secret=secret)


def _render_keys(secret: str = "", error: str = "") -> Response:
    response = make_response(
        render_template(
            "api_v1/api_keys.j2",
            title="Clés d'API",
            tokens=active_tokens(db.session, cast("User", g.user)),
            member_scopes=MEMBER_SCOPES,
            lifetimes=LIFETIMES,
            max_name_length=MAX_NAME_LENGTH,
            secret=secret,
            error=error,
            form=request.form,
        ),
        422 if error else 200,
    )
    response.cache_control.no_store = True
    return response


@preferences_blueprint.post("/api-keys/<int:token_id>/revoke")
@nav(hidden=True)
def revoke_api_key(token_id: int) -> WerkzeugResponse:
    """Revoke one of the member's own keys."""
    _revoke(ApiToken.id == token_id, ApiToken.user_id == g.user.id)
    return redirect(url_for("preferences.api_keys"))


@admin_blueprint.get("/api-keys")
@nav(parent="index", icon="key", label="Clés d'API")
def api_keys() -> str:
    """Every active key."""
    return render_template(
        "api_v1/admin_api_keys.j2",
        title="Clés d'API actives",
        tokens=active_tokens(db.session),
    )


@admin_blueprint.post("/api-keys/<int:token_id>/revoke")
@nav(hidden=True)
def admin_revoke_api_key(token_id: int) -> WerkzeugResponse:
    """Revoke anybody's key."""
    _revoke(ApiToken.id == token_id)
    return redirect(url_for("admin.api_keys"))


def _revoke(*criteria: sa.ColumnElement[bool]) -> None:
    token = db.session.scalar(sa.select(ApiToken).where(*criteria))
    if token is None:
        raise NotFound
    revoke_token(token)
    db.session.commit()
    logger.info("API key {} revoked by user {}", token.id, g.user.id)
    flash("La clé est révoquée.")


preferences_blueprint.add_url_rule(
    "/api-keys", view_func=ApiKeysView.as_view("api_keys")
)
