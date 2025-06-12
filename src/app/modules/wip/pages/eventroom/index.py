# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import scoped_session
from svcs.flask import container

from app.flask.lib.pages import page
from app.flask.routing import url_for
from app.models.mixins import Owned
from app.modules.wip.models.eventroom import Event
from app.modules.wip.pages.base import BaseWipPage
from app.modules.wip.pages.home import HomePage
from app.services.auth import AuthService

MAIN_ITEMS = [
    # 1
    {
        "id": "events",
        "model_class": Event,
        "endpoint": "EventsWipView:index",
        "label": "Evénements",
        "nickname": "EV",
        "color": "bg-pink-600",
    },
]


@page
class EventRoomPage(BaseWipPage):
    name = "eventroom"
    label = "Event'room"
    title = "Espace de rédaction des événements"
    icon = "calendar"

    template = "wip/pages/newsroom.j2"
    parent = HomePage

    def __acl__(self):
        return []
        #     ("Allow", "Everyone", "view"),
        # ]

    def context(self):
        items = MAIN_ITEMS.copy()
        for item in items:
            model_class = item["model_class"]
            item["count"] = str(self.item_count(model_class))
            item["href"] = url_for(item["endpoint"])

        return {
            "items": items,
        }

    def item_count(self, model_class: type[Owned]) -> int:
        db_session = container.get(scoped_session)
        user = container.get(AuthService).get_user()
        stmt = (
            select(func.count())
            .select_from(model_class)
            .where(model_class.owner_id == user.id)
        )
        result = db_session.execute(stmt).scalar()
        assert isinstance(result, int)
        return result
