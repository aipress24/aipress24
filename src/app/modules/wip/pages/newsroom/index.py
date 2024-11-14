# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import scoped_session
from svcs.flask import container

from app.enums import RoleEnum
from app.flask.lib.pages import page
from app.flask.routing import url_for
from app.models.mixins import Owned
from app.modules.wip.models.newsroom import (
    Article,
    AvisEnquete,
    Commande,
    JustifPublication,
    Sujet,
)
from app.services.auth import AuthService

from ..base import BaseWipPage
from ..home import HomePage

MAIN_ITEMS = [
    # 1
    {
        "id": "sujets",
        "model_class": Sujet,
        "endpoint": "SujetsWipView:index",
        "label": "Sujets",
        "nickname": "SU",
        "color": "bg-pink-600",
    },
    # 2
    {
        "id": "commandes",
        "model_class": Commande,
        "endpoint": "CommandesWipView:index",
        "label": "Commandes",
        "nickname": "CO",
        "color": "bg-green-600",
    },
    # 3
    {
        "id": "avis_enquete",
        "model_class": AvisEnquete,
        "endpoint": "AvisEnqueteWipView:index",
        "label": "Avis d'enquête",
        "nickname": "AE",
        "color": "bg-teal-600",
    },
    # 4
    {
        "id": "articles",
        "model_class": Article,
        "endpoint": "ArticlesWipView:index",
        "label": "Articles",
        "nickname": "AR",
        "color": "bg-blue-600",
    },
    # 5
    {
        "id": "publications",
        "model_class": JustifPublication,
        "label": "Justificatifs de publication",
        "nickname": "PU",
        "color": "bg-orange-600",
    },
]


@page
class NewsroomPage(BaseWipPage):
    name = "newsroom"
    label = "Newsroom"
    title = "Newsroom (espace de rédaction)"
    icon = "rocket-launch"

    allowed_roles = [RoleEnum.PRESS_MEDIA, RoleEnum.ACADEMIC]

    template = "wip/pages/newsroom.j2"
    parent = HomePage

    def context(self):
        items = MAIN_ITEMS.copy()
        for item in items:
            model_class = item["model_class"]
            item["count"] = str(self.item_count(model_class))
            if endpoint := item.get("endpoint"):
                item["href"] = url_for(endpoint)
            else:
                item["href"] = "#"

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
        return db_session.execute(stmt).scalar()
