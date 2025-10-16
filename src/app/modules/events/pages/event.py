# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

import json
from typing import cast

import arrow
from attr import define
from flask import Response, g, make_response, request
from sqlalchemy import select

from app.flask.extensions import db
from app.flask.lib.pages import Page, page
from app.flask.lib.view_model import ViewModel
from app.flask.sqla import get_multi, get_obj
from app.models.auth import User
from app.modules.events.models import EventPost
from app.modules.events.services import get_participants
from app.services.social_graph import adapt

from .events import EventsPage


@define
class EventVM(ViewModel):
    def extra_attrs(self):
        event = cast(EventPost, self._model)

        if event.published_at:
            age = event.published_at.humanize(locale="fr")
        else:
            age = "(not set)"

        participants: list[User] = get_participants(event)
        participants.sort(key=lambda u: (u.last_name, u.first_name))

        return {
            "age": age,
            #
            "author": event.owner,
            #
            "likes": event.like_count,
            "replies": event.comment_count,
            "views": event.view_count,
            "type_label": event.Meta.type_label,
            "type_id": event.Meta.type_id,
            "participants": participants,
        }


@page
class EventPage(Page):
    path = "/<int:id>"
    name = "event"
    template = "pages/event.j2"

    parent = EventsPage

    def __init__(self, id) -> None:
        self.args = {"id": id}
        self.event = get_obj(id, EventPost)
        self.view_model = EventVM(self.event)

    @property
    def label(self):
        return self.event.title

    def context(self):
        return {
            "page": self,
            "event": self.view_model,
        }

    def get_related_events(self):
        today = arrow.now().date()
        stmt = (
            select(EventPost)
            .where(EventPost.start_date >= arrow.get(today))
            .order_by(EventPost.start_date)
            .limit(10)
        )
        return get_multi(EventPost, stmt)

    def get_metadata_list(self):
        item = self.event
        return [
            {"label": "Type", "value": "Évènement"},
            {"label": "Genre", "value": item.genre or "N/A"},
            {"label": "Catégorie", "value": item.category or "N/A"},
            {"label": "Secteur d'activité", "value": item.sector or "N/A"},
            # {"label": "Rubrique", "value": item.section or "N/A"},
            # {"label": "Sujet", "value": item.topic or "N/A"},
            # {"label": "Fonction", "value": item.job or "N/A"},
            # {"label": "Compétence", "value": item.competency or "N/A"},
        ]

    #
    # Actions
    #
    def post(self) -> Response | str:
        action = request.form["action"]
        user = g.user
        article = self.event
        match action:
            case "toggle-like":
                return self.toggle_like(user, article)
            case _:
                return ""

    def toggle_like(self, user: User, article):
        social_user = adapt(user)
        if social_user.is_liking(article):
            social_user.unlike(article)
            message = f"Vous avec retiré votre 'like' au post {article.title!r}"
        else:
            social_user.like(user, article)
            message = f"Vous avez 'liké' le post {article.title!r}"
        db.session.flush()
        article.like_count = social_user.num_likes()
        db.session.commit()

        response = make_response(str(self.event.like_count))
        response.headers["HX-Trigger"] = json.dumps(
            {
                "showToast": message,
            }
        )
        return response
