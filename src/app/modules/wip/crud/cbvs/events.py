# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from typing import cast

from flask import (
    Flask,
    flash,
    g,
    redirect,
)
from flask_super.registry import register
from sqlalchemy_utils.types.arrow import arrow

from app.flask.extensions import db
from app.flask.routing import url_for
from app.models.lifecycle import PublicationStatus
from app.modules.wip.models.eventroom import Event
from app.modules.wip.models.eventroom.repositories import EventRepository
from app.signals import (
    event_published,
    event_unpublished,
    event_updated,
)

from ._base import BaseWipView
from ._forms import EventForm
from ._table import BaseTable


class EventsTable(BaseTable):
    id = "events-table"

    def __init__(self, q="") -> None:
        super().__init__(Event, q)

    def url_for(self, obj, _action="get", **kwargs):
        return url_for(f"EventsWipView:{_action}", id=obj.id, **kwargs)

    def get_actions(self, item):
        actions = [
            {
                "label": "Voir",
                "url": self.url_for(item),
            },
            {
                "label": "Modifier",
                "url": self.url_for(item, "edit"),
            },
        ]
        if item.status == PublicationStatus.DRAFT:
            actions.append(
                {
                    "label": "Publier",
                    "url": self.url_for(item, "publish"),
                }
            )
        else:
            actions.append(
                {
                    "label": "Dépublier",
                    "url": self.url_for(item, "unpublish"),
                }
            )
        actions += [
            {
                "label": "Supprimer",
                "url": self.url_for(item, "delete"),
            },
        ]
        return actions


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

    def _post_update_model(self, model: Event) -> None:
        if not model.status:
            model.status = PublicationStatus.DRAFT
            model.published_at = arrow.now("Europe/Paris")
            if g.user.organisation_id:
                model.publisher_id = g.user.organisation_id
        event_updated.send(model)

    def publish(self, id: int):
        repo = self._get_repo()
        event = cast("Event", self._get_model(id))
        event.status = PublicationStatus.PUBLIC
        repo.update(event, auto_commit=False)
        event_published.send(event)
        db.session.commit()
        flash("L'événement a été publié")
        return redirect(self._url_for("index"))

    def unpublish(self, id: int):
        repo = self._get_repo()
        event = cast("Event", self._get_model(id))
        event.status = PublicationStatus.DRAFT
        repo.update(event, auto_commit=False)
        event_unpublished.send(event)
        db.session.commit()
        flash("L'événement a été dépublié")
        return redirect(self._url_for("index"))


@register
def register_on_app(app: Flask) -> None:
    EventsWipView.register(app)
