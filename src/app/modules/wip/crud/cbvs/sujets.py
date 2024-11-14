# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from flask import Flask
from flask_super.registry import register

from app.flask.routing import url_for
from app.models.repositories import SujetRepository
from app.modules.wip.models.newsroom import Sujet

from ._base import BaseWipView
from ._forms import SujetForm
from ._table import BaseTable


class SujetsTable(BaseTable):
    id = "sujets-table"

    def __init__(self, q=""):
        super().__init__(Sujet, q)

    def url_for(self, obj, _action="get", **kwargs):
        return url_for(f"SujetsWipView:{_action}", id=obj.id, **kwargs)


class SujetsWipView(BaseWipView):
    name = "sujets"

    model_class = Sujet
    repo_class = SujetRepository
    table_class = SujetsTable
    form_class = SujetForm
    doc_type = "sujet"

    route_base = "sujets"
    path = "/wip/sujets/"

    # UI
    icon = "newspaper"

    label_main = "Newsroom: sujets"
    label_list = "Liste des sujets"
    label_new = "Créer un sujet"
    label_edit = "Modifier le sujet"

    table_id = "sujet-table-body"

    msg_delete_ok = "Le sujet a été supprimé"
    msg_delete_ko = "Vous n'êtes pas autorisé à supprimer ce sujet"


@register
def register_on_app(app: Flask):
    SujetsWipView.register(app)
