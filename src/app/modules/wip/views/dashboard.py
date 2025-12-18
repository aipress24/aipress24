# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""WIP dashboard page."""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from attr import frozen
from flask import render_template
from svcs.flask import container
from werkzeug.exceptions import Forbidden

from app.enums import RoleEnum
from app.flask.routing import url_for
from app.models.lifecycle import PublicationStatus
from app.services.auth import AuthService

from .. import blueprint
from ._common import get_secondary_menu

if TYPE_CHECKING:
    from app.services.repositories import Repository

ALLOWED_ROLES: ClassVar = [RoleEnum.PRESS_MEDIA, RoleEnum.ACADEMIC]


@blueprint.route("/dashboard")
def dashboard():
    """Tableau de bord"""
    # Lazy import to avoid circular import
    from app.modules.wip.models import ArticleRepository, CommuniqueRepository
    from app.modules.wip.pages.tables import RecentContentsTable
    from app.services.roles import has_role
    from flask import g

    user = g.user
    if not has_role(user, ALLOWED_ROLES):
        raise Forbidden("Access denied to dashboard")

    cards = _get_cards(ArticleRepository, CommuniqueRepository)
    recent_contents_table = RecentContentsTable()

    return render_template(
        "wip/pages/dashboard.j2",
        title="Mon tableau de bord",
        cards=cards,
        recent_contents_table=recent_contents_table,
        menus={"secondary": get_secondary_menu("dashboard")},
    )


def _get_cards(article_repo, communique_repo) -> list:
    """Build cards for dashboard."""
    public = PublicationStatus.PUBLIC
    draft = PublicationStatus.DRAFT

    article_public_count = _get_content_count(article_repo, public)
    article_draft_count = _get_content_count(article_repo, draft)
    communique_public_count = _get_content_count(communique_repo, public)
    communique_draft_count = _get_content_count(communique_repo, draft)
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


def _get_content_count(repository: type["Repository"], status: PublicationStatus) -> int:
    """Get count of content for repository."""
    repo = container.get(repository)
    auth = container.get(AuthService)
    user = auth.get_user()
    return repo.count(status=status, owner_id=user.id)


@frozen
class Card:
    """Card data for dashboard display."""

    label: str
    icon: str
    value: int
    href: str
