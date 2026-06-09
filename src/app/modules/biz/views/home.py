# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Biz home (Marketplace) view."""

from __future__ import annotations

import sqlalchemy as sa
from flask import g, render_template, request
from sqlalchemy.orm import InstrumentedAttribute

from app.enums import RoleEnum
from app.flask.extensions import db
from app.flask.routing import url_for
from app.flask.sqla import get_multi
from app.models.lifecycle import PublicationStatus
from app.modules.biz import blueprint
from app.modules.biz.models import (
    EditorialProduct,
    JobOffer,
    MarketplaceContent,
    MissionCategory,
    MissionOffer,
    ProjectOffer,
)
from app.modules.biz.views._common import (
    FILTER_SPECS,
    JOURNALISM_FILTER_SPECS,
    TABS,
)
from app.modules.kyc.ontology_loader import get_choices as get_ontology_choices
from app.services.roles import has_role


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
                sa.select(EditorialProduct)
                .where(EditorialProduct.status == PublicationStatus.PUBLIC)
                .limit(30)
            )
            return get_multi(EditorialProduct, stmt)
        case "missions":
            stmt = (
                sa.select(MissionOffer)
                .where(MissionOffer.status == PublicationStatus.PUBLIC)
                .order_by(MissionOffer.created_at.desc())
                .limit(30)
            )
            # Bug #0186 — Journalism missions are visible only to
            # PRESS_MEDIA. Other communities don't get to know what
            # journalists post. NULL category (back-compat) stays
            # visible to everyone.
            if not has_role(g.user, RoleEnum.PRESS_MEDIA):
                stmt = stmt.where(
                    sa.or_(
                        MissionOffer.category.is_(None),
                        MissionOffer.category != MissionCategory.JOURNALISME,
                    )
                )
            return get_multi(MissionOffer, stmt)
        case "projects":
            stmt = (
                sa.select(ProjectOffer)
                .where(ProjectOffer.status == PublicationStatus.PUBLIC)
                .order_by(ProjectOffer.created_at.desc())
                .limit(30)
            )
            return get_multi(ProjectOffer, stmt)
        case "jobs":
            stmt = (
                sa.select(JobOffer)
                .where(JobOffer.status == PublicationStatus.PUBLIC)
                .order_by(JobOffer.created_at.desc())
                .limit(30)
            )
            return get_multi(JobOffer, stmt)
        case _:
            return []


def _get_filters() -> list[dict]:
    """Build filter options using efficient DISTINCT queries.

    Ticket #0202 — when the user is on the Missions tab AND has picked
    the JOURNALISME category (`?category=journalisme`), the
    journalism-specific filter set is appended after the generic ones.
    """
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

    if _journalism_filters_active():
        for spec in JOURNALISM_FILTER_SPECS:
            options: list[dict] = []
            if spec.get("options"):
                options = [{"id": o, "label": o} for o in spec["options"]]
            elif "ontology_key" in spec:
                try:
                    choices = get_ontology_choices(spec["ontology_key"])
                except Exception:
                    choices = []
                if isinstance(choices, list):
                    for c in choices:
                        if isinstance(c, tuple) and len(c) == 2:
                            options.append({"id": c[0], "label": c[1]})
                        elif isinstance(c, str):
                            options.append({"id": c, "label": c})
            result.append(
                {"id": spec["id"], "label": spec["label"], "options": options}
            )

    return result


def _journalism_filters_active() -> bool:
    """The expanded journalism filter set is shown only on the
    Missions tab when the JOURNALISME category is selected."""
    return (
        request.args.get("current_tab", "stories") == "missions"
        and request.args.get("category", "") == "journalisme"
    )


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
