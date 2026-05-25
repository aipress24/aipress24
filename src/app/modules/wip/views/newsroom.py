# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""WIP newsroom page."""

from __future__ import annotations

from typing import Any

from flask import g, render_template
from werkzeug.exceptions import Forbidden

from app.enums import ProfileEnum, RoleEnum
from app.flask.lib.nav import nav
from app.flask.routing import url_for
from app.modules.bw.bw_activation.user_utils import get_business_wall_for_user
from app.modules.wip import blueprint
from app.modules.wip.pr_access import (
    user_can_access_newsroom,
    user_is_acting_as_pr_manager,
)
from app.services.roles import has_role

from ._common import count_owned_non_deleted, get_secondary_menu

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


@blueprint.route("/newsroom")
@nav(icon="rocket-launch", acl=[("Allow", RoleEnum.PRESS_MEDIA, "view")])
def newsroom():
    """Newsroom"""
    # Lazy import to avoid circular import
    from app.modules.wip.models import (
        Article,
        AvisEnquete,
        Commande,
        Sujet,
    )

    # Check ACL
    user = g.user
    if not user_can_access_newsroom(user):
        msg = "Access denied to newsroom"
        raise Forbidden(msg)

    main_items = [
        {
            "id": "sujets",
            "model_class": Sujet,
            "endpoint": "SujetsWipView:index",
            "label": "Sujets",
            "nickname": "SU",
            "color": "bg-pink-600",
        },
        {
            "id": "commandes",
            "model_class": Commande,
            "endpoint": "CommandesWipView:index",
            "label": "Commandes",
            "nickname": "CO",
            "color": "bg-green-600",
        },
        {
            "id": "avis_enquete",
            "model_class": AvisEnquete,
            "endpoint": "AvisEnqueteWipView:index",
            "label": "Avis d'enquête",
            "nickname": "AE",
            "color": "bg-teal-600",
        },
        {
            "id": "articles",
            "model_class": Article,
            "endpoint": "ArticlesWipView:index",
            "label": "Articles",
            "nickname": "AR",
            "color": "bg-blue-600",
        },
    ]

    items = _allowed_redaction_items(main_items)
    for item in items:
        model_class = item["model_class"]
        item["count"] = str(count_owned_non_deleted(model_class))
        if endpoint := item.get("endpoint"):
            item["href"] = url_for(endpoint)
        else:
            item["href"] = "#"

    return render_template(
        "wip/pages/newsroom.j2",
        title="Newsroom (espace de rédaction)",
        items=items,
        menus={"secondary": get_secondary_menu("newsroom")},
    )


def _allowed_redaction_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Filter items based on user permissions."""
    allow_journalist = _check_article_creation_by_journalist()
    allow_commands = _check_command_creation_by_redac_chief()
    has_bw = _has_active_business_wall()

    # PR managers acting for another BW can also publish sujets,
    # avis d'enquêtes and commandes
    is_pr_manager = user_is_acting_as_pr_manager(g.user)
    allow_sujet = allow_journalist or is_pr_manager
    allow_avis = allow_journalist or is_pr_manager
    allow_commande = allow_commands or is_pr_manager

    items = _filter_articles_items(items, [has_bw, allow_journalist])
    items = _filter_sujets_items(items, [has_bw, allow_sujet])
    items = _filter_avis_enquetes_items(items, [has_bw, allow_avis])
    items = _filter_commandes_items(items, [has_bw, allow_commande])
    return items


def _has_active_business_wall() -> bool:
    """True if user's organisation has an active Business Wall."""
    bw = get_business_wall_for_user(g.user)
    return bw is not None


def _check_article_creation_by_journalist() -> bool:
    """True if user is allowed to create articles."""
    profile = g.user.profile
    try:
        profile_enum = ProfileEnum[profile.profile_code]
    except KeyError:
        return False
    return profile_enum in ALLOW_NEWSROOM_ARTICLE


def _check_command_creation_by_redac_chief() -> bool:
    """True if user is allowed to create commands."""
    profile = g.user.profile
    try:
        profile_enum = ProfileEnum[profile.profile_code]
    except KeyError:
        return False
    return profile_enum in ALLOW_NEWSROOM_COMMAND


def _filter_articles_items(
    items: list[dict[str, Any]], flags: list[bool]
) -> list[dict[str, Any]]:
    if not all(flags):
        items = [item for item in items if item["id"] != "articles"]
    return items


def _filter_sujets_items(
    items: list[dict[str, Any]], flags: list[bool]
) -> list[dict[str, Any]]:
    if not all(flags):
        items = [item for item in items if item["id"] != "sujets"]
    return items


def _filter_avis_enquetes_items(
    items: list[dict[str, Any]], flags: list[bool]
) -> list[dict[str, Any]]:
    if not all(flags):
        items = [item for item in items if item["id"] != "avis_enquete"]
    return items


def _filter_commandes_items(
    items: list[dict[str, Any]], flags: list[bool]
) -> list[dict[str, Any]]:
    if not all(flags):
        items = [item for item in items if item["id"] != "commandes"]
    return items
