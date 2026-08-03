# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Biz home (Marketplace) view."""

from __future__ import annotations

import sqlalchemy as sa
from flask import g, render_template, request
from sqlalchemy.orm import InstrumentedAttribute
from svcs.flask import container

from app.enums import RoleEnum
from app.flask.extensions import db
from app.flask.routing import url_for
from app.models.lifecycle import PublicationStatus
from app.modules.biz import blueprint
from app.modules.biz.models import (
    EditorialProduct,
    MarketplaceContent,
    MissionCategory,
    MissionOffer,
)
from app.modules.biz.repositories import (
    EditorialProductRepository,
    JobOfferRepository,
    MissionOfferRepository,
    ProjectOfferRepository,
)
from app.modules.biz.views._common import (
    DEADLINE_OPTIONS,
    GENERIC_FILTER_SPECS,
    JOURNALISM_FILTER_SPECS,
    TABS,
)
from app.modules.biz.views._filters import (
    JobFilterBar,
    MissionFilterBar,
    ProjectFilterBar,
    get_euro_options,
    get_filter_conditions,
    get_job_filter_conditions,
    get_mission_filter_conditions,
)
from app.modules.kyc.ontology_loader import get_choices as get_ontology_choices
from app.services.roles import has_role

DEFAULT_BUDGETS = ["1000", "10000"]


@blueprint.route("/", methods=["GET", "POST"])
def biz():
    """Marketplace."""
    current_tab = request.args.get("current_tab", "subscriptions")
    project_filter_bar = ProjectFilterBar()
    job_filter_bar = JobFilterBar()
    mission_filter_bar = MissionFilterBar()
    if request.method == "POST":
        if current_tab == "projects":
            project_filter_bar.update_state()
        elif current_tab == "jobs":
            job_filter_bar.update_state()
        elif current_tab == "missions":
            mission_filter_bar.update_state()

    ctx = {
        "objs": _get_objs(project_filter_bar, job_filter_bar, mission_filter_bar),
        "tabs": _get_tabs(),
        "filters": _get_filters(project_filter_bar, job_filter_bar, mission_filter_bar),
        "project_filter_bar": project_filter_bar,
        "job_filter_bar": job_filter_bar,
        "mission_filter_bar": mission_filter_bar,
        "title": "Marketplace",
    }
    if request.method == "POST" and request.headers.get("Hx-Target") == "content":
        return render_template("pages/biz-home--content.j2", **ctx)
    return render_template("pages/biz-home.j2", **ctx)


def _get_objs(
    project_filter_bar: ProjectFilterBar | None = None,
    job_filter_bar: JobFilterBar | None = None,
    mission_filter_bar: MissionFilterBar | None = None,
) -> list[MarketplaceContent]:
    """Get marketplace objects for display (limited to 30, newest first).

    Delegates the "publicly visible" gate to the marketplace repositories
    (status-only, per ``is_public(MarketplaceContent)``) rather than restating
    it inline.
    """
    current_tab = request.args.get("current_tab", "subscriptions")
    match current_tab:
        case "subscriptions":
            repo = container.get(EditorialProductRepository)
            rows, _ = repo.list_public(limit=30, offset=0)
            return list(rows)
        case "missions":
            # Bug #0186 — Journalism missions are visible only to PRESS_MEDIA.
            # Other communities don't get to know what journalists post. NULL
            # category (back-compat) stays visible to everyone.
            extra = []
            if not has_role(g.user, RoleEnum.PRESS_MEDIA):
                extra.append(
                    sa.or_(
                        MissionOffer.category.is_(None),
                        MissionOffer.category != MissionCategory.JOURNALISME,
                    )
                )
            if mission_filter_bar:
                extra.extend(get_mission_filter_conditions(mission_filter_bar))
            repo = container.get(MissionOfferRepository)
            rows, _ = repo.list_public(*extra, limit=30, offset=0)
            return list(rows)
        case "projects":
            repo = container.get(ProjectOfferRepository)
            extra = (
                get_filter_conditions(project_filter_bar) if project_filter_bar else []
            )
            rows, _ = repo.list_public(*extra, limit=30, offset=0)
            return list(rows)
        case "jobs":
            repo = container.get(JobOfferRepository)
            extra = get_job_filter_conditions(job_filter_bar) if job_filter_bar else []
            rows, _ = repo.list_public(*extra, limit=30, offset=0)
            return list(rows)
        case _:
            return []


def _get_filters(
    project_filter_bar: ProjectFilterBar | None = None,
    job_filter_bar: JobFilterBar | None = None,
    mission_filter_bar: MissionFilterBar | None = None,
) -> list[dict]:
    """Build filter options using efficient DISTINCT queries.

    When on the Missions tab, replaced generic filters by mission
    specific filters (Type, Secteur, Pays, Département, Ville).

    When on the Projects tab, replaced generic filters by project
    specific filters (Type, Secteur, Pays, Département, Ville).

    When on the Jobs tab, replaced generic filters by job specific
    filters (Secteur, Type contrat, Pays, Département, Ville).
    """
    current_tab = request.args.get("current_tab", "subscriptions")

    if current_tab == "missions":
        if mission_filter_bar is None:
            mission_filter_bar = MissionFilterBar()
        result = list(mission_filter_bar.filters)
        # special case for Journalisme: more filters
        if _journalism_filters_active(mission_filter_bar):
            for spec in JOURNALISM_FILTER_SPECS:
                filter_id = spec["id"]
                options: list[dict] = []
                if filter_id in ("budget_min", "budget_max"):
                    options = _get_budget_options(filter_id)
                elif filter_id == "deadline":
                    options = DEADLINE_OPTIONS
                elif spec.get("options"):
                    options = [{"id": o, "label": o} for o in spec["options"]]
                elif "ontology_key" in spec:
                    used_values = _get_distinct_json_values(MissionOffer, filter_id)
                    try:
                        choices = get_ontology_choices(spec["ontology_key"])
                    except Exception:
                        choices = []
                    if isinstance(choices, list):
                        for c in choices:
                            cid, clabel = (
                                (c[0], c[1])
                                if isinstance(c, tuple) and len(c) == 2
                                else (c, c)
                            )
                            if (
                                not used_values
                                or cid in used_values
                                or clabel in used_values
                            ):
                                options.append({"id": cid, "label": clabel})
                result.append(
                    {"id": filter_id, "label": spec["label"], "options": options}
                )
        return result

    if current_tab == "projects":
        if project_filter_bar is None:
            project_filter_bar = ProjectFilterBar()
        return project_filter_bar.filters

    if current_tab == "jobs":
        if job_filter_bar is None:
            job_filter_bar = JobFilterBar()
        # Use the method to refresh after POST toggle.
        return job_filter_bar.get_filters()

    result = []
    for spec in GENERIC_FILTER_SPECS:
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


def _journalism_filters_active(
    mission_filter_bar: MissionFilterBar | None = None,
) -> bool:
    """The expanded journalism filter set is shown on the Missions tab when the
    JOURNALISME category is selected."""
    if request.args.get("current_tab", "subscriptions") != "missions":
        return False
    if request.args.get("category", "") == "journalisme":
        return True

    return bool(
        mission_filter_bar
        and mission_filter_bar.has_filter("type_mission", "journalisme")
    )


def _get_distinct_json_values(model: type, column_name: str) -> set[str]:
    """Return distinct values stored in a JSON list column."""
    column = getattr(model, column_name, None)
    if column is None:
        return set()
    stmt = (
        sa.select(column)
        .where(model.status == PublicationStatus.PUBLIC)
        .where(column.is_not(None))
    )
    rows = db.session.scalars(stmt).all()
    values = set()
    for row in rows:
        if isinstance(row, list):
            for item in row:
                if item:
                    values.add(str(item))
    return values


def _get_budget_options(column_name: str) -> list[dict[str, str]]:
    """Return budget options from DB values merged with defaults."""
    return get_euro_options(MissionOffer, column_name, DEFAULT_BUDGETS)


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
    current_tab = request.args.get("current_tab", "subscriptions")
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
