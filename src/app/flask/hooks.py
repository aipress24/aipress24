# Copyright (c) 2021-2024 - Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

import importlib.metadata

import requests
from devtools import debug
from flask import Flask, current_app, g, redirect, request
from flask_login import current_user, login_user
from flask_security.core import AnonymousUser
from jose import jwt
from sqlalchemy import select
from svcs.flask import container
from werkzeug.exceptions import Unauthorized

from app.flask.extensions import db
from app.flask.routing import url_for
from app.flask.sqla import get_obj
from app.models.auth import User
from app.modules.iam.constants import API_KEY, JKS, JWT_COOKIE
from app.services.menus import MenuService
from app.services.notifications import NotificationService
from app.services.promotions import get_promotion

TIMEOUT = 5


def register_hooks(app: Flask) -> None:
    app.before_request(inject_extensions)
    app.before_request(authenticate_user)
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
        g.user = current_user._get_current_object()
        return

    cookies = request.cookies
    token = cookies.get(JWT_COOKIE)
    if not token:
        g.user = AnonymousUser()
        return

    payload = jwt.decode(token, JKS, algorithms=["RS256"])
    user_id = payload["userId"]
    url = f"https://api.userfront.com/v0/users/{user_id}"
    # debug(payload)
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {API_KEY}",
    }
    response = requests.get(url, headers=headers, timeout=TIMEOUT)
    user_json = response.json()
    user_email = user_json.get("email")
    if not user_email:
        g.user = AnonymousUser()
        return

    stmt = select(User).where(User.email == user_email)
    result = db.session.execute(stmt)
    user = result.scalar_one_or_none()
    if not user:
        print(f"Creating user {user_email}")
        user = User(email=user_email)
        debug(user.id)
        db.session.add(user)
        db.session.commit()
    else:
        print(f"Found user {user_email}")
    login_user(user, force=True)
    g.user = user


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
