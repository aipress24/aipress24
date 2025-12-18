# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Biz home (Marketplace) view."""

from __future__ import annotations

import sqlalchemy as sa
from flask import render_template, request

from app.flask.components.filterset import FilterSet
from app.flask.routing import url_for
from app.flask.sqla import get_multi
from app.models.lifecycle import PublicationStatus
from app.modules.biz import blueprint
from app.modules.biz.models import MarketplaceContent
from app.modules.biz.views._common import FILTER_SPECS, TABS


@blueprint.route("/")
def biz():
    """Marketplace"""
    objs = _get_objs()
    ctx = {
        "objs": objs,
        "tabs": _get_tabs(),
        "filters": _get_filters(),
        "title": "Marketplace",
    }
    return render_template("pages/biz-home.j2", **ctx)


def _get_objs():
    """Get marketplace objects based on current tab."""
    current_tab = request.args.get("current_tab", "stories")
    match current_tab:
        case "stories":
            stmt = (
                sa.select(MarketplaceContent)
                .where(MarketplaceContent.status == PublicationStatus.PUBLIC)
                .limit(30)
            )
            return get_multi(MarketplaceContent, stmt)
        case _:
            return []


def _get_filters():
    """Build filter set for marketplace content."""
    stmt = sa.select(MarketplaceContent).where(
        MarketplaceContent.status == PublicationStatus.PUBLIC
    )
    articles = get_multi(MarketplaceContent, stmt)

    filter_set = FilterSet(FILTER_SPECS)
    filter_set.init(articles)

    return filter_set.get_filters()


def _get_tabs() -> list[dict]:
    """Build tabs with current tab state."""
    current_tab = request.args.get("current_tab", "stories")
    tabs = []
    for tab in TABS:
        tab_id = tab["id"]
        tabs.append(
            {
                "id": tab_id,
                "label": tab["label"],
                "href": url_for(".biz", current_tab=tab_id),
                "current": tab_id == current_tab,
            }
        )
    return tabs
