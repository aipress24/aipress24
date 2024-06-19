# Copyright (c) 2021-2024 - Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from flask import redirect, render_template, request

from app.flask.routing import url_for

from .. import get, route
from .steps import Step, get_step
from .steps.step1 import Step1


@get("/")
def index():
    return redirect(url_for(".wiz"))


@get("/wiz/")
def wiz():
    step = Step1()
    return redirect(url_for(".step", step_id=step.id))


@route("/wiz/<step_id>", methods=["GET", "POST"])
def step(step_id: str):
    step = get_step(step_id)
    match request.method:
        case "GET":
            return step_get(step)

        case "POST":
            return step_post(step)

        case _:
            raise NotImplementedError


def step_get(step: Step):
    ctx = {
        "title": step.title,
        "content": step.render(),
    }
    return render_template("kyc/_layout.html", **ctx)


def step_post(step: Step):
    form_data = request.form

    if step.id == "step1":
        data = dict(form_data)
        del data["_next"]
        if not data:
            return redirect(url_for(".step", step_id="step1"))

    # form = step.form_class(form_data, meta={"csrf": False})
    # is_valid = form.validate()

    if "_next" in form_data:
        next_step_id = step.get_next_step_id()
        if next_step_id:
            return redirect(url_for(".step", step_id=next_step_id))
        else:
            return redirect(url_for(".confirm"))

    if "_prev" in form_data:
        prev_step_id = step.prev_step_id
        return redirect(url_for(".step", step_id=prev_step_id))

    return None
