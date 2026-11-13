# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from flask import redirect, render_template
from flask_login import current_user

from app.flask.routing import url_for
from app.modules.public import get


@get("/")
def home():
    if not current_user.is_anonymous:
        return redirect(url_for("wire.wire"))
    return redirect(url_for("security.login"))


@get("/pricing/")
def pricing():
    return render_template("pages/pricing.j2")
