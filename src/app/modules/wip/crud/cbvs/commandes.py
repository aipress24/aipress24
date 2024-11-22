# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from flask import Flask
from flask_super.registry import register

from app.flask.routing import url_for
from app.models.repositories import CommandeRepository
from app.modules.wip.models.newsroom import Commande

from ._base import BaseWipView
from ._forms import CommandeForm
from ._table import BaseTable


class CommandesTable(BaseTable):
    id = "commandes-table"

    def __init__(self, q=""):
        super().__init__(Commande, q)

    def url_for(self, obj, _action="get", **kwargs):
        return url_for(f"CommandesWipView:{_action}", id=obj.id, **kwargs)


class CommandesWipView(BaseWipView):
    name = "commandes"

    model_class = Commande
    repo_class = CommandeRepository
    table_class = CommandesTable
    form_class = CommandeForm
    doc_type = "commande"

    route_base = "commandes"
    path = "/wip/commandes/"

    # UI
    label_main = "Newsroom: commandes"
    label_list = "Liste des commandes"
    label_new = "Créer une commande"
    label_view = "Voir la commande"
    label_edit = "Modifier la commande"
    table_id = "commande-table-body"

    msg_delete_ok = "La commande a été supprimée"
    msg_delete_ko = "Vous n'êtes pas autorisé à supprimer cette commande"

    icon = "newspaper"


@register
def register_on_app(app: Flask):
    CommandesWipView.register(app)
