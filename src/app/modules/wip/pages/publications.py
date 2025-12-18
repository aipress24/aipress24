# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

import webargs
from flask import g, jsonify, request
from sqlalchemy import select
from webargs.flaskparser import parser

from app.flask.lib.pages import expose, page
from app.flask.routing import url_for
from app.flask.sqla import get_multi
from app.models.content.base import BaseContent
from app.ui.labels import make_label

from .base import BaseWipPage
from .home import HomePage

__all__ = ["PublicationsPage"]

TABLE_COLUMNS = [
    {"name": "date", "label": "Date", "width": 50},
    {"name": "type", "label": "Type", "width": 50},
    {"name": "title", "label": "Titre", "width": 50},
]

OPTIONS = [
    {"value": "press-release", "label": "Rédiger un communiqué"},
    #
    {"value": "press-event", "label": "Annoncer un évènement presse"},
    {"value": "public-event", "label": "Annoncer un évènement public"},
    {"value": "training-event", "label": "Annoncer une formation"},
    {"value": "contest-event", "label": "Annoncer un concours"},
    #
    {"value": "xxx", "label": "Poster une annonce de mission de communication"},
    {"value": "xxx", "label": "Poster une annonce de projet"},
    #
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


# Disabled: migrated to views/publications.py
# @page
class PublicationsPage(BaseWipPage):
    name = "alt-content"
    label = "Autres publications"
    icon = "pencil-alt"

    template = "wip/pages/newsroom.j2"
    parent = HomePage

    def context(self):
        table = {
            "columns": TABLE_COLUMNS,
            "data_source": url_for(".newsroom__json_data"),
        }
        return {
            "table": table,
            "options": OPTIONS,
        }

    # def context(self):
    #     stmt = (
    #         select(BaseContent)
    #         .where(BaseContent.status == "draft")
    #         .where(BaseContent.owner_id == g.user.id)
    #     )
    #     objects = list(get_multi(BaseContent, stmt))
    #
    #     lines = [
    #         {
    #             "url": "#",
    #             "columns": [
    #                 obj.created_at.format("YYYY/MM/DD"),
    #                 TYPE_LABELS[obj.type],
    #                 obj.title,
    #             ],
    #         }
    #         for obj in objects
    #     ]
    #     table = {
    #         "specs": TABLE["specs"],
    #         "lines": lines,
    #     }
    #     return {"table": table, "tabs": []}

    @expose
    def json_data(self):
        args = parser.parse(json_data_args, request, location="query")
        search = args["search"].lower()

        # stmt = select(func.count()).select_from(Group)
        # if args["search"]:
        #     search = args["search"].lower()
        #     stmt = stmt.filter(Group.name.ilike(f"{search}%"))
        # result = db.session.execute(stmt)
        # total = result.first()[0]
        total = 1000  # TODO

        stmt = (
            select(BaseContent)
            # .where(BaseContent.status == PublicationStatus.DRAFT)
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


LABELS_FOR_CONTENT_TYPES = {
    "article": "Article",
    "press-release": "Communiqué de presse",
    "press-event": "Evénement de presse",
    "public-event": "Evénement public",
    "training-event": "Formation",
    "editorial-product": "Produit éditorial",
}

# @page
# class CreateContentPage(WipPage):
#     name = "create_content"
#     label = "Nouveau contenu"
#     icon = "pencil-alt"
#
#     parent = WipPublicationsPage
#
#     @property
#     def title(self) -> str:
#         content_type = request.args.get("type", "article")
#         label = LABELS_FOR_CONTENT_TYPES.get(content_type)
#         return f"Nouveau contenu de type: {label}"
#
#     def context(self):
#         options = {
#             "genres": GENRES,
#             "topics": MEDIA_TOPICS,
#             "sections": PRESS_SECTIONS,
#             "sectors": SECTORS,
#             "jobs": JOBS,
#             "competencies": COMPETENCIES,
#             "locations": ["TODO"],
#         }
#
#         return {
#             "options": options,
#         }
#
#     def content(self, ctx):
#         content_type = request.args.get("type", "article")
#         if "/" in content_type:
#             raise BadRequest()
#
#         file = f"{content_type}.toml"
#         return Form.from_file(file).render(None, ctx)
#
#     def post(self):
#         debug(dict(**request.form))
#         return redirect(url_for(".newsroom"))
