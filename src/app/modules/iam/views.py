# Copyright (c) 2021-2024 - Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from flask import redirect, render_template, request
from flask_login import logout_user
from jose import jwt
from snoop import pp

from app.flask.routing import url_for

from . import blueprint, constants


#
# UserFront
#
@blueprint.route("/login")
def login():
    cookies = request.cookies
    token = cookies.get(constants.JWT_COOKIE)
    pp(token)
    return render_template("iam/userfront/login.html")


@blueprint.route("/signup")
def signup():
    return render_template("iam/userfront/signup.html")


@blueprint.route("/logout")
def logout():
    cookies = request.cookies
    pp(dict(cookies))
    logout_user()
    response = redirect(url_for("iam.login"))
    response.set_cookie(constants.JWT_COOKIE, "", expires=0)
    response.set_cookie("access.zn5r464b", "", expires=0)
    response.set_cookie("id.zn5r464b", "", expires=0)
    response.set_cookie("refresh.zn5r464b", "", expires=0)
    response.set_cookie("session", "", expires=0)
    return response


@blueprint.route("/debug")
def debug() -> str:
    cookies = request.cookies
    token = cookies.get(constants.JWT_COOKIE)
    if not token:
        return "No cookie"

    payload = jwt.decode(token, constants.JKS, algorithms=["RS256"])
    pp(payload)
    return "OK"
