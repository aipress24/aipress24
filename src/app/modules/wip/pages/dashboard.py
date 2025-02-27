# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from attr import frozen
from svcs.flask import container

from app.enums import RoleEnum
from app.flask.lib.pages import page
from app.flask.routing import url_for
from app.models.lifecycle import PublicationStatus
from app.models.repositories import ArticleRepository
from app.modules.wip.pages.tables import RecentContentsTable
from app.services.auth import AuthService

from .base import BaseWipPage
from .home import HomePage

__all__ = ["DashboardPage"]


@page
class DashboardPage(BaseWipPage):
    name = "dashboard"
    label = "Tableau de bord"
    title = "Mon tableau de bord"
    icon = "chart-bar"

    parent = HomePage

    allowed_roles = [RoleEnum.PRESS_MEDIA, RoleEnum.ACADEMIC]

    def context(self):
        return {
            "cards": self.get_cards(),
            "recent_contents_table": RecentContentsTable(),
            # "recent_transactions_table": RecentTransactionsTable(),
        }

    def get_cards(self):
        public = PublicationStatus.PUBLIC
        draft = PublicationStatus.DRAFT
        return [
            Card(
                "Articles publiés",
                "newspaper",
                self.get_articles_count(public),
                url_for("ArticlesWipView:index"),
            ),
            Card(
                "Articles en cours",
                "pencil-square",
                self.get_articles_count(draft),
                url_for("ArticlesWipView:index"),
            ),
            Card(
                "Articles vendus",
                "banknotes",
                0,
                url_for("ArticlesWipView:index"),
            ),
        ]

    def get_articles_count(self, status: PublicationStatus):
        repo = container.get(ArticleRepository)
        auth = container.get(AuthService)
        user = auth.get_user()
        return repo.count(status=status, owner_id=user.id)


@frozen
class Card:
    label: str
    icon: str
    value: int
    href: str
