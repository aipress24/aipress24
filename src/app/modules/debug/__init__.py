# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

import json
import os

from flask import Blueprint, current_app
from werkzeug.exceptions import Unauthorized

blueprint = Blueprint("debug", __name__, url_prefix="/debug")
get = blueprint.get
route = blueprint.route


@blueprint.before_request
def check_debug() -> None:
    config = current_app.config
    unsecure = config.get("UNSECURE", False)
    if not unsecure:
        raise Unauthorized


@blueprint.get("/")
def debug():
    def default(o) -> str:
        return str(o)

    config_ = dict(sorted(current_app.config.items()))
    env_ = dict(sorted(os.environ.items()))

    d = {"config": config_, "env": env_}
    e = json.dumps(d, default=default, indent=2)
    return e, 200, {"Content-Type": "application/json"}


@blueprint.route("/db")
def db():
    response = {
        "SQLALCHEMY_DATABASE_URI": current_app.config["SQLALCHEMY_DATABASE_URI"],
        "DB": str(db),
        "DB_ENGINE": str(db.engine),
    }
    return json.dumps(response), 200, {"Content-Type": "application/json"}


@get("/env")
def env():
    environment = dict(os.environ)
    response = []
    for key, value in sorted(environment.items()):
        response.append(f"{key}={value}")
    return "<pre>\n" + "\n".join(response) + "\n</pre>"


@get("/config")
def config():
    config = current_app.config
    response = []
    for key, value in sorted(config.items()):
        response.append(f"{key}={value}")
    return "<pre>\n" + "\n".join(response) + "\n</pre>"
