# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from flask import Flask
from flask_super.registry import register

from app.flask.routing import url_for
from app.modules.wip.models import Communique, CommuniqueRepository

from ._base import BaseWipView
from ._forms import CommuniqueForm
from ._table import BaseTable


class CommuniquesTable(BaseTable):
    id = "communiques-table"

    def __init__(self, q="") -> None:
        super().__init__(Communique, q)

    def url_for(self, obj, _action="get", **kwargs):
        return url_for(f"CommuniquesWipView:{_action}", id=obj.id, **kwargs)


class CommuniquesWipView(BaseWipView):
    name = "communiques"

    model_class = Communique
    repo_class = CommuniqueRepository
    table_class = CommuniquesTable
    form_class = CommuniqueForm
    doc_type = "communique"

    route_base = "communiques"
    path = "/wip/communiques/"

    # UI
    icon = "megaphone"

    label_main = "Com'room: communiqués"
    label_list = "Liste des communiqués"
    label_new = "Créer un communiqué"
    label_edit = "Modifier le communiqué"
    label_view = "Voir le communiqué"

    table_id = "communique-table-body"

    msg_delete_ok = "Le communiqué a été supprimé"
    msg_delete_ko = "Vous n'êtes pas autorisé à supprimer ce communiqué"


@register
def register_on_app(app: Flask) -> None:
    CommuniquesWipView.register(app)
