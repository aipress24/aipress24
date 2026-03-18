# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Biz home (Marketplace) view."""

from __future__ import annotations

import sqlalchemy as sa
from flask import render_template, request
from sqlalchemy.orm import InstrumentedAttribute

from app.flask.extensions import db
from app.flask.routing import url_for
from app.flask.sqla import get_multi
from app.models.lifecycle import PublicationStatus
from app.modules.biz import blueprint
from app.modules.biz.models import EditorialProduct, MarketplaceContent
from app.modules.biz.views._common import FILTER_SPECS, TABS


@blueprint.route("/")
def biz():
    """Marketplace."""
    ctx = {
        "objs": _get_objs(),
        "tabs": _get_tabs(),
        "filters": _get_filters(),
        "title": "Marketplace",
    }
    return render_template("pages/biz-home.j2", **ctx)


def _get_objs() -> list[MarketplaceContent]:
    """Get marketplace objects for display (limited to 30)."""
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


def _get_filters() -> list[dict]:
    """Build filter options using efficient DISTINCT queries."""
    result = []
    for spec in FILTER_SPECS:
        filter_id = spec["id"]
        label = spec["label"]

        # Use hardcoded options if provided
        if "options" in spec:
            options = [{"id": opt, "label": opt} for opt in spec["options"]]
        # Otherwise, query distinct values from database
        elif "selector" in spec:
            column_name = spec["selector"]
            distinct_values = _get_distinct_values(column_name)
            options = [{"id": v, "label": v} for v in distinct_values if v]
        else:
            options = []

        result.append({"id": filter_id, "label": label, "options": options})

    return result


def _get_distinct_values(column_name: str) -> list[str]:
    """Query distinct non-empty values for a column from public marketplace items."""
    # Columns like sector, topic, genre are on EditorialProduct, not MarketplaceContent
    column: InstrumentedAttribute | None = getattr(EditorialProduct, column_name, None)
    if column is None:
        return []

    stmt = (
        sa.select(column)
        .where(EditorialProduct.status == PublicationStatus.PUBLIC)
        .where(column != "")
        .where(column.is_not(None))
        .distinct()
        .order_by(column)
    )

    return list(db.session.scalars(stmt))


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
