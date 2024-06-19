# Copyright (c) 2021-2024 - Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

import json
from typing import Any

from flask import make_response, render_template

from .. import blueprint


@blueprint.route("/sandbox/tiny")
def tiny():
    content = render_template("sandbox/tiny.j2")
    menus: dict[str, Any] = {"main": [], "create": [], "user": []}
    ctx = {
        "content": content,
        "title": "",
        "menus": menus,
        "breadcrumbs": [],
    }
    return render_template("layout/private.j2", **ctx)


@blueprint.route("/sandbox/trix")
def trix():
    content = render_template("sandbox/trix.j2")
    menus: dict[str, Any] = {"main": [], "create": [], "user": []}
    ctx = {
        "content": content,
        "title": "",
        "menus": menus,
        "breadcrumbs": [],
    }
    return render_template("layout/private.j2", **ctx)


@blueprint.route("/sandbox")
def sandbox():
    content = render_template("pages/sandbox.j2")
    menus: dict[str, Any] = {"main": [], "create": [], "user": []}
    ctx = {
        "content": content,
        "title": "",
        "menus": menus,
        "breadcrumbs": [],
    }
    response = make_response(render_template("layout/private.j2", **ctx))
    response.headers["HX-Trigger"] = json.dumps(
        {
            "showToast": "I am a toaster message!",
        }
    )
    return response


@blueprint.route("/sandbox2")
def sandbox2():
    content = render_template("pages/sandbox2.j2")
    menus: dict[str, Any] = {"main": [], "create": [], "user": []}
    ctx = {
        "content": content,
        "title": "",
        "menus": menus,
        "breadcrumbs": [],
    }
    response = make_response(render_template("layout/private.j2", **ctx))
    return response


@blueprint.route("/sandboxx")
def sandboxx():
    content = ""
    menus: dict[str, Any] = {"main": [], "create": [], "user": []}
    ctx = {
        "content": content,
        "title": "",
        "menus": menus,
        "breadcrumbs": [],
    }
    response = make_response(render_template("layout/private.j2", **ctx))
    response.headers["HX-Trigger"] = json.dumps(
        {
            "ticketCounterHasChanged": "-",
            "showToast": "I am a toaster message!",
        }
    )
    return response


@blueprint.route("/sandbox3/")
def sandbox3():
    return render_template("pages/sandbox3.j2")
