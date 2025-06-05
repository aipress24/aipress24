# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from typing import Any

from flask import current_app, g
from sqlalchemy import func, select
from sqlalchemy.orm import scoped_session
from svcs.flask import container

from app.enums import ProfileEnum, RoleEnum
from app.flask.lib.pages import page
from app.flask.routing import url_for
from app.models.mixins import Owned
from app.modules.wip.models import (
    Article,
    AvisEnquete,
    Commande,
    Sujet,
)
from app.modules.wip.pages.base import BaseWipPage
from app.modules.wip.pages.home import HomePage
from app.services.auth import AuthService

ALLOW_NEWSROOM_ARTICLE: set[ProfileEnum] = {
    ProfileEnum.PM_DIR,
    ProfileEnum.PM_JR_CP_SAL,
    ProfileEnum.PM_JR_PIG,
    ProfileEnum.PM_JR_CP_ME,
    ProfileEnum.PM_JR_ME,
    ProfileEnum.PM_DIR_SYND,
}

ALLOW_NEWSROOM_COMMAND: set[ProfileEnum] = {
    ProfileEnum.PM_DIR,
    ProfileEnum.PM_JR_CP_SAL,
    ProfileEnum.PM_JR_PIG,
    ProfileEnum.PM_JR_CP_ME,
    ProfileEnum.PM_JR_ME,
    ProfileEnum.PM_DIR_SYND,
}


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
    # TODO LATER
    # {
    #     "id": "publications",
    #     "model_class": JustifPublication,
    #     "label": "Justificatifs de publication",
    #     "nickname": "PU",
    #     "color": "bg-orange-600",
    # },
]


@page
class NewsroomPage(BaseWipPage):
    name = "newsroom"
    label = "Newsroom"
    title = "Newsroom (espace de rédaction)"
    icon = "rocket-launch"

    template = "wip/pages/newsroom.j2"
    parent = HomePage

    def __acl__(self):
        return [
            ("Allow", RoleEnum.PRESS_MEDIA, "view"),
            ("Deny", "Everyone", "view"),
        ]

    def context(self):
        items = self.allowed_redaction_items()
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

    def allowed_redaction_items(self) -> list[dict[str, Any]]:
        items = MAIN_ITEMS

        allow_journalist = self._check_article_creation_by_journalist()
        allow_commands = self._check_command_creation_by_redac_chief()
        # Temps, to allow testing without business wall
        if current_app.debug:
            return items

        has_bw = self._has_active_business_wall()

        items = self.filter_articles_items(items, [has_bw, allow_journalist])
        items = self.filter_sujets_items(items, [has_bw, allow_journalist])
        items = self.filter_avis_enquetes_items(items, [has_bw, allow_journalist])
        items = self.filter_avis_commandes_items(items, [has_bw, allow_commands])
        return items

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

    @staticmethod
    def _has_active_business_wall() -> bool:
        """True if the current user's organisation has an active Business Wall."""
        org = g.user.organisation
        if not org:
            return False
        return org.is_bw_active

    @staticmethod
    def _check_article_creation_by_journalist() -> bool:
        """True if the current user is allowed to create articles.

        Only journalists can create or manage articles or sujets
        in newsroom.
        """
        profile = g.user.profile
        profile_enum = ProfileEnum[profile.profile_code]
        return profile_enum in ALLOW_NEWSROOM_ARTICLE

    @staticmethod
    def _check_command_creation_by_redac_chief() -> bool:
        """Only Chief editors (and journalists) can create or
        manage commandes in newsroom.
        """
        profile = g.user.profile
        profile_enum = ProfileEnum[profile.profile_code]
        return profile_enum in ALLOW_NEWSROOM_COMMAND

    def filter_articles_items(
        self,
        items: list[dict[str, Any]],
        flags: list[bool],
    ) -> list[dict[str, Any]]:
        if not all(flags):
            items = [item for item in items if item["id"] != "articles"]
        return items

    def filter_sujets_items(
        self,
        items: list[dict[str, Any]],
        flags: list[bool],
    ) -> list[dict[str, Any]]:
        if not all(flags):
            items = [item for item in items if item["id"] != "sujets"]
        return items

    def filter_avis_enquetes_items(
        self,
        items: list[dict[str, Any]],
        flags: list[bool],
    ) -> list[dict[str, Any]]:
        if not all(flags):
            items = [item for item in items if item["id"] != "avis_enquete"]
        return items

    def filter_avis_commandes_items(
        self,
        items: list[dict[str, Any]],
        flags: list[bool],
    ) -> list[dict[str, Any]]:
        if not all(flags):
            items = [item for item in items if item["id"] != "commandes"]
        return items
