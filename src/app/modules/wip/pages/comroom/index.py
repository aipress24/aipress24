# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from app.enums import RoleEnum
from app.flask.lib.pages import page
from app.flask.routing import url_for

from ..base import BaseWipPage
from ..home import HomePage

MAIN_ITEMS = [
    # # 1
    # {
    #     "id": "sujets",
    #     "model_class": Sujet,
    #     "endpoint": "SujetsWipView:index",
    #     "label": "Sujets",
    #     "nickname": "SU",
    #     "color": "bg-pink-600",
    # },
    # # 2
    # {
    #     "id": "commandes",
    #     "model_class": Commande,
    #     "endpoint": "CommandesWipView:index",
    #     "label": "Commandes",
    #     "nickname": "CO",
    #     "color": "bg-green-600",
    # },
    # # 3
    # {
    #     "id": "avis_enquete",
    #     "model_class": AvisEnquete,
    #     "endpoint": "AvisEnqueteWipView:index",
    #     "label": "Avis d'enquête",
    #     "nickname": "AE",
    #     "color": "bg-teal-600",
    # },
    # # 4
    # {
    #     "id": "articles",
    #     "model_class": Article,
    #     "endpoint": "ArticlesWipView:index",
    #     "label": "Articles",
    #     "nickname": "AR",
    #     "color": "bg-blue-600",
    # },
    # # 5
    # # TODO LATER
    # # {
    # #     "id": "publications",
    # #     "model_class": JustifPublication,
    # #     "label": "Justificatifs de publication",
    # #     "nickname": "PU",
    # #     "color": "bg-orange-600",
    # # },
]


@page
class ComroomPage(BaseWipPage):
    name = "comroom"
    label = "Com'room"
    title = "Com'room (espace de rédaction pour les RP)"
    icon = "rocket-launch"

    # allowed_roles = [RoleEnum.PRESS_RELATIONS]

    template = "wip/pages/newsroom.j2"
    parent = HomePage

    def __acl__(self):
        return [
            ("Allow", RoleEnum.PRESS_RELATIONS, "view"),
            ("Deny", "Everyone", "view"),
        ]

    def context(self):
        # items = self.allowed_redaction_items()
        items = []
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
