# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""WIP publications page."""

from __future__ import annotations

import webargs
from flask import g, jsonify, render_template, request
from sqlalchemy import select
from webargs.flaskparser import parser

from app.flask.routing import url_for
from app.flask.sqla import get_multi
from app.models.content.base import BaseContent
from app.ui.labels import make_label

from .. import blueprint
from ._common import get_secondary_menu

TABLE_COLUMNS = [
    {"name": "date", "label": "Date", "width": 50},
    {"name": "type", "label": "Type", "width": 50},
    {"name": "title", "label": "Titre", "width": 50},
]

OPTIONS = [
    {"value": "press-release", "label": "Rédiger un communiqué"},
    {"value": "press-event", "label": "Annoncer un évènement presse"},
    {"value": "public-event", "label": "Annoncer un évènement public"},
    {"value": "training-event", "label": "Annoncer une formation"},
    {"value": "contest-event", "label": "Annoncer un concours"},
    {"value": "xxx", "label": "Poster une annonce de mission de communication"},
    {"value": "xxx", "label": "Poster une annonce de projet"},
    {"value": "xxx", "label": "Poster une offre d'emploi dans le journalisme"},
    {"value": "xxx", "label": "Poster une demande d'emploi dans le journalisme"},
    {"value": "xxx", "label": "Poster une offre d'emploi dans la communication"},
    {"value": "xxx", "label": "Poster une demande d'emploi dans la communication"},
    {"value": "xxx", "label": "Poster une offre de stage dans le journalisme"},
    {"value": "xxx", "label": "Poster une demande de stage dans le journalisme"},
    {"value": "xxx", "label": "Poster une offre de stage dans la communication"},
    {"value": "xxx", "label": "Poster une demande de stage dans la communication"},
]

json_data_args = {
    "limit": webargs.fields.Int(load_default=15),
    "offset": webargs.fields.Int(load_default=0),
    "search": webargs.fields.Str(load_default=""),
}


@blueprint.route("/alt-content", endpoint="alt-content")
def publications():
    """Autres publications"""
    table = {
        "columns": TABLE_COLUMNS,
        "data_source": url_for(".publications_json_data"),
    }
    return render_template(
        "wip/pages/newsroom.j2",
        title="Autres publications",
        table=table,
        options=OPTIONS,
        menus={"secondary": get_secondary_menu("alt-content")},
    )


@blueprint.route("/alt-content/json_data")
def publications_json_data():
    """JSON data for publications table."""
    args = parser.parse(json_data_args, request, location="query")
    search = args["search"].lower()

    total = 1000  # TODO: Calculate actual total

    stmt = (
        select(BaseContent)
        .where(BaseContent.owner_id == g.user.id)
        .offset(args["offset"])
        .limit(args["limit"])
    )

    if search:
        stmt = stmt.filter(BaseContent.title.ilike(f"%{search}%"))

    objects: list[BaseContent] = list(get_multi(BaseContent, stmt))

    data = [
        {
            "$url": url_for(obj),
            "id": obj.id,
            "title": obj.title,
            "date": obj.created_at.format("YYYY/MM/DD"),
            "type": make_label(obj.type),
        }
        for obj in objects
    ]
    return jsonify(data=data, total=total)
