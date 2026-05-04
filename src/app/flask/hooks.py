# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

import importlib.metadata

from flask import Flask, current_app, g, redirect, request, session
from flask_login import current_user
from flask_security.core import AnonymousUser
from flask_security.signals import user_authenticated
from svcs.flask import container
from werkzeug.exceptions import NotFound, Unauthorized

from app.flask.doorman import doorman
from app.flask.lib.proxies import unproxy
from app.flask.routing import url_for
from app.flask.sqla import get_obj
from app.lib.debugging import debug
from app.models.auth import User
from app.services.menus import MenuService
from app.services.notifications import NotificationService
from app.services.promotions import PromotionService
from app.settings import get_settings

TIMEOUT = 5

# Session keys whose prefix indicates per-module UI state (search
# filters, active tab, sort, etc). Cleared at every login so a
# user never inherits the previous occupant's view of a list.
# Ref: bug #0118 — events filter persisted across users.
_PER_USER_SESSION_KEY_PREFIXES: tuple[str, ...] = (
    "events:",
    "wire:",
    "swork:",
    "biz:",
)


def register_hooks(app: Flask) -> None:
    app.before_request(inject_extensions)
    app.before_request(authenticate_user)
    app.before_request(doorman.check_access)
    app.context_processor(inject_extra_context)
    app.errorhandler(Unauthorized)(handle_authentication_error)
    user_authenticated.connect(_clear_per_user_session_state, app)

    # app.after_request(dump_session)
    # template_rendered.connect_via(app)(log_template_info)


def _clear_per_user_session_state(_sender, **_kwargs) -> None:
    """Drop all `<module>:<key>` session entries on login.

    Flask-Security keeps the same browser session cookie when one
    user logs out and another logs in (only the auth identifiers
    are rotated). Without this hook, UI state stored under module
    prefixes (e.g. `events:state`, `wire:tab`) would leak between
    users sharing a browser.
    """
    for key in list(session.keys()):
        if key.startswith(_PER_USER_SESSION_KEY_PREFIXES):
            session.pop(key, None)


def inject_extensions() -> None:
    g.extensions = current_app.extensions


def handle_authentication_error(_e):
    return redirect(url_for("security.login"))


def authenticate_user() -> None:
    if request.path.startswith("/static"):
        return

    if current_user.is_authenticated:
        g.user = unproxy(current_user)
        return

    # In test mode, try to use a default test user (ID 0) if it exists
    # This is a fallback for tests that don't explicitly authenticate
    if current_app.testing:
        try:
            g.user = get_obj(0, User)
            return
        except NotFound:
            # If user 0 doesn't exist, continue to anonymous user
            pass

    g.user = AnonymousUser()
    return


def inject_extra_context():
    menu_service = container.get(MenuService)
    notification_service = container.get(NotificationService)
    promotion_service = container.get(PromotionService)

    try:
        version = importlib.metadata.version("aipress24-flask")
    except importlib.metadata.PackageNotFoundError:
        version = "???"

    def get_notifications() -> list:
        return notification_service.get_notifications(g.user)

    def get_unread_notification_count() -> int:
        if not getattr(g, "user", None) or g.user.is_anonymous:
            return 0
        return notification_service.get_unread_count(g.user)

    return {
        "get_promotion": promotion_service.get_promotion,
        "url_for": url_for,
        "json_data": {},
        "app_version": version,
        "menus": menu_service,
        "get_notifications": get_notifications,
        "get_unread_notification_count": get_unread_notification_count,
        "settings": get_settings(),
    }


#
# Debugging
#
def dump_session(response):
    # debug(sorted(session.items()))
    return response


def log_template_info(_sender, **kwargs) -> None:
    template = kwargs["template"]
    context = kwargs["context"]
    debug(template.name, list(context.keys()))
