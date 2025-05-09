# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from flask import current_app, redirect, render_template, request, session
from flask_security import login_user
from werkzeug.exceptions import Forbidden, NotFound

from app.flask.extensions import db
from app.flask.routing import url_for
from app.models.auth import User
from app.modules.public import get


def check_unsecure() -> None:
    """Check the application is in "unsecure" mode, i.e. not in production."""
    unsecure = current_app.config.get("UNSECURE", False)
    if not unsecure:
        msg = "This is not an unsecure environment"
        raise Forbidden(msg)


@get("/backdoor/")
def backdoor():
    check_unsecure()
    session.clear()
    role = request.args.get("role")
    if role:
        return render_template("pages/backdoor-banner.j2", title="Backdoor", role=role)
    return render_template("pages/backdoor.j2", title="Backdoor")


@get("/backdoor/<role>")
def backdoor_login(role):
    role = role.upper()
    check_unsecure()
    users = db.session.query(User).order_by(User.id).all()
    for user in users:
        if user.has_role(role):
            login_user(user)
            db.session.commit()
            return redirect(url_for("wire.wire"))

    msg = f"Role {role} not found"
    raise NotFound(msg)
