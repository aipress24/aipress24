# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from flask import Flask
from flask_super.registry import register

from app.flask.routing import url_for
from app.modules.wip.models.eventroom import Event
from app.modules.wip.models.eventroom.repositories import EventRepository

from ._base import BaseWipView
from ._forms import EventForm
from ._table import BaseTable


class EventsTable(BaseTable):
    id = "events-table"

    def __init__(self, q="") -> None:
        super().__init__(Event, q)

    def url_for(self, obj, _action="get", **kwargs):
        return url_for(f"EventsWipView:{_action}", id=obj.id, **kwargs)


class EventsWipView(BaseWipView):
    name = "events"

    model_class = Event
    repo_class = EventRepository
    table_class = EventsTable
    form_class = EventForm
    doc_type = "event"

    route_base = "events"
    path = "/wip/events/"

    # UI
    icon = "calendar"

    label_main = "Evénements"
    label_list = "Liste des événements"
    label_new = "Créer un événement"
    label_edit = "Modifier l'événement"
    label_view = "Voir l'événement"

    table_id = "events-table-body"

    msg_delete_ok = "L'événement a été supprimé"
    msg_delete_ko = "Vous n'êtes pas autorisé à supprimer cet événement"


@register
def register_on_app(app: Flask) -> None:
    EventsWipView.register(app)
