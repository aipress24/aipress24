# Copyright (c) 2025, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only
"""Public, versioned REST API for third-party integrations (``/api/v1``).

This module is deliberately isolated: it depends on the business modules
(wire, events, biz, bw, swork, core models/services) but nothing depends on
it. It is auto-discovered through the ``register_on_app`` hook rather than
the plain ``blueprint`` attribute, so flask-smorest can collect its OpenAPI
paths — see :func:`register_on_app`.

Design summary:

- **Read-only** in v1. The only write is a best-effort ``last_used_at`` stamp
  on the authenticating token.
- **Token auth** via ``Authorization: Bearer <token>`` (see :mod:`.security`);
  session cookies are ignored, so the API is not CSRF-exposed.
- **Scoped**: each resource requires a capability scope on the token.
- **JSON errors**: auth failures short-circuit ``before_request`` with a JSON
  body instead of the app's global HTML login redirect.
"""

from __future__ import annotations

from flask import Flask, current_app, jsonify, make_response, request
from flask.wrappers import Response
from flask_smorest import Api, Blueprint
from flask_super.registry import register
from werkzeug.exceptions import HTTPException
from werkzeug.http import HTTP_STATUS_CODES
from werkzeug.wrappers import Response as WerkzeugResponse

from app.flask.extensions import db

from .security import parse_bearer_header, resolve_token, set_identity, touch

__all__ = ["blp", "register_on_app"]


class ScopedApi(Api):
    """A flask-smorest ``Api`` that does not hijack app-wide error handling.

    The stock ``Api`` registers a JSON handler for *every* ``HTTPException``
    on the whole app, which would turn the HTML site's 404s into JSON. We
    suppress that and instead register our own path-scoped handler
    (:func:`_handle_http_exception`) that emits JSON only for ``/api/v1``.
    """

    def _register_error_handlers(self) -> None:
        return


blp = Blueprint(
    "api_v1",
    __name__,
    url_prefix="/api/v1",
    description="AIpress24 public API — read-only access to published content, "
    "organisations and member profiles.",
)

# Endpoints reachable without a token (the discovery entrypoint). The OpenAPI
# document and doc UIs are served by the smorest ``Api`` on the app, not by
# this blueprint, so they are already public.
AUTH_EXEMPT_ENDPOINTS = frozenset({"api_v1.root"})


# --- JSON error envelope (matches flask-smorest's error shape) ------------


def json_error(status_code: int, message: str) -> Response:
    payload = {
        "code": status_code,
        "status": HTTP_STATUS_CODES.get(status_code, "Error"),
        "message": message,
    }
    return make_response(jsonify(payload), status_code)


def _unauthorized(message: str) -> Response:
    response = json_error(401, message)
    response.headers["WWW-Authenticate"] = 'Bearer realm="api"'
    return response


def _handle_http_exception(exc: HTTPException) -> WerkzeugResponse:
    """Render ``/api/v1`` errors as JSON; leave the HTML site untouched.

    Registered app-wide for ``HTTPException`` (so it also catches routing-level
    404/405 that never reach the blueprint), but scoped by path: non-API
    requests get Werkzeug's default response, and because this handler is
    registered for the *base* ``HTTPException`` it never shadows the app's
    more-specific handlers (e.g. the ``Unauthorized`` login redirect).
    """
    if not request.path.startswith("/api/v1"):
        return exc.get_response()

    code = exc.code or 500
    payload = {
        "code": code,
        "status": HTTP_STATUS_CODES.get(code, "Error"),
        "message": exc.description,
    }
    data = getattr(exc, "data", None)
    if isinstance(data, dict):
        if data.get("message"):
            payload["message"] = data["message"]
        errors = data.get("errors") or data.get("messages")
        if errors:
            payload["errors"] = errors
    return make_response(jsonify(payload), code)


# --- authentication (blueprint-scoped, token only) ------------------------


@blp.before_request
def authenticate() -> Response | None:
    """Resolve the bearer token or short-circuit with a JSON 401."""
    if request.endpoint in AUTH_EXEMPT_ENDPOINTS:
        return None

    raw_token = parse_bearer_header(request.headers.get("Authorization"))
    if not raw_token:
        return _unauthorized("Missing bearer token.")

    session = db.session
    token = resolve_token(raw_token, session)
    if token is None:
        return _unauthorized("Invalid, expired or revoked token.")

    # Best-effort last-seen stamp. A failure here must not fail the request.
    touch(token)
    try:
        session.commit()
    except Exception:
        session.rollback()

    set_identity(token)
    return None


# --- app wiring -----------------------------------------------------------


def _default_config() -> dict[str, object]:
    return {
        "API_TITLE": "AIpress24 API",
        "API_VERSION": "1.0",
        "OPENAPI_VERSION": "3.0.3",
        "OPENAPI_URL_PREFIX": "/api/v1",
        "OPENAPI_JSON_PATH": "openapi.json",
        "OPENAPI_SWAGGER_UI_PATH": "/docs",
        "OPENAPI_SWAGGER_UI_URL": "https://cdn.jsdelivr.net/npm/swagger-ui-dist/",
        "OPENAPI_REDOC_PATH": "/redoc",
        "OPENAPI_REDOC_URL": (
            "https://cdn.jsdelivr.net/npm/redoc@next/bundles/redoc.standalone.js"
        ),
    }


def _configure_security_scheme(api: Api) -> None:
    api.spec.components.security_scheme(
        "BearerAuth",
        {
            "type": "http",
            "scheme": "bearer",
            "description": "An AIpress24 API token, sent as `Authorization: "
            "Bearer <token>`.",
        },
    )
    # Apply the scheme globally; the public discovery endpoint overrides it.
    api.spec.options.setdefault("security", [{"BearerAuth": []}])


@register
def register_on_app(app: Flask) -> None:
    """Create the smorest ``Api`` and register the API blueprint.

    Registered via flask-super's ``@register`` and invoked from
    ``register_everything_else`` (app factory). Using this hook — rather than
    exposing a top-level ``blueprint`` attribute — is what lets flask-smorest
    collect the OpenAPI paths (a plain ``app.register_blueprint`` would not).
    """
    for key, value in _default_config().items():
        app.config.setdefault(key, value)

    # Import route modules so their @blp.route decorators have run before the
    # blueprint is registered. (Idempotent: modules are import-cached.)
    from . import resources  # noqa: F401

    api = ScopedApi(app)
    _configure_security_scheme(api)
    # Render API errors as JSON without disturbing the HTML site. Registered on
    # the (fresh) app rather than the shared blueprint, so register_on_app stays
    # re-entrant across multiple create_app() calls in one process.
    app.register_error_handler(HTTPException, _handle_http_exception)
    api.register_blueprint(blp)


def current_openapi_json() -> dict:
    """Return the generated OpenAPI document (used by the CLI export)."""
    apis = current_app.extensions["flask-smorest"]["apis"]
    api: Api = next(iter(apis.values()))["ext_obj"]
    return api.spec.to_dict()
