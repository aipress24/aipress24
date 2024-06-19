# Copyright (c) 2021-2024 - Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

import importlib.metadata
import json
import os

from flask import current_app, redirect, render_template, request, session
from flask_security import login_user
from werkzeug.exceptions import Forbidden, NotFound

from app.flask.extensions import db
from app.flask.routing import url_for
from app.models.auth import User

from .. import blueprint


def check_unsecure():
    unsecure = current_app.config.get("UNSECURE", False)
    if not unsecure:
        raise Forbidden("This is not an unsecure environment")


@blueprint.get("/version/")
def version():
    return importlib.metadata.version("aipress24-flask")


@blueprint.get("/backdoor/")
def backdoor():
    check_unsecure()
    session.clear()
    role = request.args.get("role")
    if role:
        return render_template("pages/backdoor-banner.j2", title="Backdoor", role=role)
    else:
        return render_template("pages/backdoor.j2", title="Backdoor")


@blueprint.get("/backdoor/<role>")
def backdoor_login(role):
    role = role.upper()
    check_unsecure()
    users = db.session.query(User).all()
    for user in users:
        if user.has_role(role):
            login_user(user)
            db.session.commit()
            return redirect(url_for("wire.wire"))
    raise NotFound(f"Role {role} not found")


@blueprint.get("/debug/")
def debug():
    check_unsecure()

    def default(o) -> str:
        return str(o)

    config_ = dict(sorted(current_app.config.items()))
    env_ = dict(sorted(os.environ.items()))

    d = {"config": config_, "env": env_}
    e = json.dumps(d, default=default, indent=2)
    return e, 200, {"Content-Type": "application/json"}


@blueprint.route("/debug2/")
def debug2():
    check_unsecure()

    d = {
        "SQLALCHEMY_DATABASE_URI": current_app.config["SQLALCHEMY_DATABASE_URI"],
        "DB": str(db),
        "DB_ENGINE": str(db.engine),
    }
    return json.dumps(d), 200, {"Content-Type": "application/json"}
