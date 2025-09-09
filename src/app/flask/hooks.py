# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

import importlib.metadata

from flask import Flask, current_app, g, redirect, request
from flask_login import current_user
from flask_security.core import AnonymousUser
from svcs.flask import container
from werkzeug.exceptions import Unauthorized

from app.flask.doorman import doorman
from app.flask.lib.proxies import unproxy
from app.flask.routing import url_for
from app.flask.sqla import get_obj
from app.lib.debugging import debug
from app.models.auth import User
from app.services.menus import MenuService
from app.services.notifications import NotificationService
from app.services.promotions import get_promotion
from app.settings import get_settings

TIMEOUT = 5


def register_hooks(app: Flask) -> None:
    app.before_request(inject_extensions)
    app.before_request(authenticate_user)
    app.before_request(doorman.check_access)
    app.context_processor(inject_extra_context)
    app.errorhandler(Unauthorized)(handle_authentication_error)

    # app.after_request(dump_session)
    # template_rendered.connect_via(app)(log_template_info)


def inject_extensions() -> None:
    g.extensions = current_app.extensions


def handle_authentication_error(_e):
    return redirect(url_for("security.login"))


def authenticate_user() -> None:
    if request.path.startswith("/static"):
        return

    if current_app.testing:
        g.user = get_obj(0, User)
        return

    if current_user.is_authenticated:
        g.user = unproxy(current_user)
        return

    g.user = AnonymousUser()
    return


def inject_extra_context():
    menu_service = container.get(MenuService)
    notification_service = container.get(NotificationService)

    try:
        version = importlib.metadata.version("aipress24-flask")
    except importlib.metadata.PackageNotFoundError:
        version = "???"

    def get_notifications() -> list:
        return notification_service.get_notifications(g.user)

    return {
        "get_promotion": get_promotion,
        "url_for": url_for,
        "json_data": {},
        "app_version": version,
        "menus": menu_service,
        "get_notifications": get_notifications,
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
