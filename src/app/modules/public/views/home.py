# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from typing import cast

from flask import redirect, render_template
from flask_login import current_user

from app.flask.routing import url_for
from app.models.auth import User

from .. import get


@get("/")
def home():
    user = cast("User", current_user)
    if not user.is_anonymous:
        return redirect(url_for("wire.wire"))
    else:
        return redirect(url_for("security.login"))


@get("/pricing/")
def pricing():
    return render_template("pages/pricing.j2")
