# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from attr import frozen
from svcs.flask import container

from app.enums import RoleEnum
from app.flask.routing import url_for
from app.models.lifecycle import PublicationStatus
from app.modules.wip.models import ArticleRepository, CommuniqueRepository
from app.modules.wip.pages.tables import RecentContentsTable
from app.services.auth import AuthService

from .base import BaseWipPage
from .home import HomePage

if TYPE_CHECKING:
    from app.services.repositories import Repository


__all__ = ["DashboardPage"]


# Disabled: migrated to views/dashboard.py
# @page
class DashboardPage(BaseWipPage):
    name = "dashboard"
    label = "Tableau de bord"
    title = "Mon tableau de bord"
    icon = "chart-bar"

    parent = HomePage

    allowed_roles: ClassVar = [RoleEnum.PRESS_MEDIA, RoleEnum.ACADEMIC]

    def context(self):
        return {
            "cards": self.get_cards(),
            "recent_contents_table": RecentContentsTable(),
            # "recent_transactions_table": RecentTransactionsTable(),
        }

    def get_cards(self):
        public = PublicationStatus.PUBLIC
        draft = PublicationStatus.DRAFT

        article_public_count = self.get_articles_count(public)
        article_draft_count = self.get_articles_count(draft)
        communique_public_count = self.get_communique_count(public)
        communique_draft_count = self.get_communique_count(draft)
        sold_count = 0

        cards = []
        if article_public_count > 0:
            cards.append(
                Card(
                    "Articles publiés",
                    "newspaper",
                    article_public_count,
                    url_for("ArticlesWipView:index"),
                )
            )
        if article_draft_count > 0:
            cards.append(
                Card(
                    "Articles en cours",
                    "pencil-square",
                    article_draft_count,
                    url_for("ArticlesWipView:index"),
                )
            )
        if sold_count > 0:
            cards.append(
                Card(
                    "Articles vendus",
                    "banknotes",
                    sold_count,
                    url_for("ArticlesWipView:index"),
                )
            )
        if communique_public_count > 0:
            cards.append(
                Card(
                    "Communiqués publiés",
                    "megaphone",
                    communique_public_count,
                    url_for("CommuniquesWipView:index"),
                )
            )
        if communique_draft_count > 0:
            cards.append(
                Card(
                    "Communiqués en cours",
                    "pencil-square",
                    communique_draft_count,
                    url_for("CommuniquesWipView:index"),
                )
            )

        return cards

    def get_content_count(
        self, repository: Repository, status: PublicationStatus
    ) -> int:
        repo = container.get(repository)
        auth = container.get(AuthService)
        user = auth.get_user()
        return repo.count(status=status, owner_id=user.id)

    def get_articles_count(self, status: PublicationStatus) -> int:
        return self.get_content_count(ArticleRepository, status)

    def get_communique_count(self, status: PublicationStatus):
        return self.get_content_count(CommuniqueRepository, status)


@frozen
class Card:
    label: str
    icon: str
    value: int
    href: str
