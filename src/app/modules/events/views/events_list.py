# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Events list view."""

from __future__ import annotations

import re
from collections import defaultdict

import arrow
import webargs
from attrs import asdict
from flask import g, render_template, request
from flask.views import MethodView
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.sql import Select
from webargs.flaskparser import parser

from app.flask.extensions import db, htmx
from app.flask.sqla import get_multi
from app.models.lifecycle import PublicationStatus
from app.modules.events import blueprint
from app.modules.events.models import EventPost
from app.modules.events.services import accredited_event_ids, accredited_ids_among

from ._common import Calendar, DateFilter, EventListVM
from ._filters import FILTER_SPECS, FilterBar

LIST_ARGS = {
    "month": webargs.fields.Str(load_default=""),
    "day": webargs.fields.Str(load_default=""),
    "search": webargs.fields.Str(load_default=""),
    "loc": webargs.fields.Str(load_default=""),
}


class EventsListView(MethodView):
    """Liste des événements."""

    def get(self):
        filter_bar = FilterBar()

        # HTMX boosted = full page reload, regular htmx = partial update
        if htmx.boosted:
            return self._render_events_page(filter_bar)

        if htmx:
            return self._handle_htmx_get(filter_bar)

        return self._render_events_page(filter_bar)

    def post(self):
        filter_bar = FilterBar()
        filter_bar.update_state()

        ctx = self._build_context(filter_bar)

        if request.headers.get("Hx-Target") == "body":
            return render_template("pages/events.j2", **ctx)

        return render_template("pages/events--content.j2", **ctx)

    def _handle_htmx_get(self, filter_bar: FilterBar) -> str:
        """Handle HTMX GET requests (partial updates)."""
        if "tag" in request.args:
            tag = request.args["tag"]
            filter_bar.reset()
            filter_bar.set_tag(tag)

        if request.headers.get("Hx-Target") == "members-list":
            ctx = self._build_context(filter_bar)
            return render_template("pages/events--search-results.j2", **ctx)

        return self._render_events_page(filter_bar)

    def _render_events_page(self, filter_bar: FilterBar) -> str:
        """Render full events page."""
        ctx = self._build_context(filter_bar)
        return render_template("pages/events.j2", **ctx)

    def _build_context(self, filter_bar: FilterBar) -> dict:
        """Build context for events templates."""
        args = parser.parse(LIST_ARGS, request, location="query")
        search = args["search"]
        date_filter = DateFilter(args)

        events_list = self._get_events(date_filter, filter_bar, search)

        # §7.2 — une seule requête pour toute la page, pas une par
        # carte : la pastille « Accrédité.e » ne vaut pas N requêtes.
        accredited = accredited_ids_among(g.user, [e.id for e in events_list])

        # Group events by day
        grouper = defaultdict(list)
        for event in events_list:
            event._is_accredited = event.id in accredited
            vm = EventListVM(event)
            grouper[vm.date].append(vm)

        month = date_filter.month

        return {
            "grouped_events": sorted(grouper.items()),
            "search": search,
            "calendar": asdict(Calendar(month)),
            "title": "Evénements",
            "filter_bar": filter_bar,
            "user_agenda_events": self._get_user_agenda_events(),
        }

    def _get_user_agenda_events(self) -> list[EventPost]:
        """Bug #0148: the "Votre agenda" widget used to be a hard-coded
        "Vous ne vous êtes encore inscrit à aucun événement" message,
        even when the user had been accredited to events.

        Erick (2026-05-18): a first fix only listed *future*
        participations, so members still never saw the events they had
        attended — this widget is the only place an accredited event
        surfaces. List every accredited event (past included).

        Stéfane (2026-05-20): « les plus proches en premier » — order
        by absolute distance to *now*, regardless of past/future. A
        yesterday's event (J−1) outranks a next-week's event (J+6).
        Ties broken in favour of the upcoming side; events without a
        start_datetime sink to the bottom.
        """
        user = getattr(g, "user", None)
        if user is None or getattr(user, "is_anonymous", True):
            return []
        stmt = (
            select(EventPost)
            .where(EventPost.id.in_(accredited_event_ids([user.id])))
            .where(EventPost.status == PublicationStatus.PUBLIC)
        )
        events = list(db.session.scalars(stmt))

        now = arrow.now()

        def _proximity_key(event: EventPost) -> tuple[int, float, int]:
            if event.start_datetime is None:
                return (1, 0.0, 0)
            delta = (event.start_datetime - now).total_seconds()
            past_tiebreak = 0 if delta >= 0 else 1
            return (0, abs(delta), past_tiebreak)

        events.sort(key=_proximity_key)
        return events

    def _get_events(
        self, date_filter: DateFilter, filter_bar: FilterBar, search: str
    ) -> list[EventPost]:
        """Query events with filters applied."""
        # Bug 0129: also eager-load publisher so the event card can render
        # the client/publisher name without firing N+1 queries.
        stmt = (
            select(EventPost)
            .where(EventPost.status == PublicationStatus.PUBLIC)
            .order_by(EventPost.start_datetime)
            .options(
                selectinload(EventPost.owner),
                selectinload(EventPost.publisher),
            )
        )

        stmt = date_filter.apply(stmt)
        stmt = self._apply_filter_bar(stmt, filter_bar)
        stmt = self._apply_search(stmt, search)

        return list(get_multi(EventPost, stmt))

    def _apply_filter_bar(self, stmt: Select, filter_bar: FilterBar) -> Select:
        """Restreindre la requête selon les filtres actifs.

        Piloté par `FILTER_SPECS`, et non par une liste tenue à part :
        cette fonction énumérait autrefois cinq identifiants en dur et
        ignorait silencieusement les autres. Les deux axes ajoutés au
        lot C5 — rubrique et type d'info — s'affichaient donc, leurs
        options se calculaient, et sélectionner une valeur ne changeait
        rien. Déclarer un filtre suffit désormais à le rendre agissant.
        """
        selected: dict[str, list[str]] = {}
        for f in filter_bar.active_filters:
            selected.setdefault(f["id"], []).append(f["value"])

        for spec in FILTER_SPECS:
            values = selected.get(spec["id"])
            if not values:
                continue
            column = getattr(EventPost, spec["column"])
            stmt = stmt.where(column.in_(values))

        return stmt

    def _apply_search(self, stmt: Select, search: str) -> Select:
        """Apply global search filter.

        Searches both title and postal code. If the search term contains
        numbers, also searches by postal code.
        """
        from sqlalchemy import or_

        if not search:
            return stmt

        # Always search by title
        title_filter = EventPost.title.ilike(f"%{search}%")

        # Also search by postal code if search contains numbers
        m = re.search(r"([0-9]+)", search)
        if m:
            zip_code = m.group(1)
            postal_filter = EventPost.code_postal.ilike(f"%{zip_code}%")
            return stmt.where(or_(title_filter, postal_filter))

        return stmt.where(title_filter)


# Register the view
blueprint.add_url_rule("/", view_func=EventsListView.as_view("events"))
