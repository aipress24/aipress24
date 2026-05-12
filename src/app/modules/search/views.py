# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Search page: thin layer over ``SearchEngine``.

The route accepts ``qs`` (the query string) and ``filter`` (the
collection name from :data:`COLLECTIONS`). Renders one section per
type when ``filter=all``, or a single section otherwise. The sidebar
shows per-type counts driven by ``engine.count(qs, type=…)``.

Empty queries render the page with zero hits and a hint to type
something — running BM25 on an empty query is wasteful and produces a
useless empty result page.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import arrow
import svcs.flask
from flask import current_app, render_template, request
from loguru import logger

from app.flask.routing import url_for
from app.modules.search import blueprint
from app.modules.search.constants import COLLECTIONS
from app.modules.search.engine import SearchEngine

if TYPE_CHECKING:
    from datetime import datetime

_DEFAULT_LIMIT = 20


@blueprint.route("/")
def search():
    """Rechercher"""
    qs = request.args.get("qs", "").strip()
    filter_name = request.args.get("filter", "all")

    _warn_if_semantic_requested()

    if not qs:
        return render_template(
            "pages/search.j2",
            title="Rechercher",
            qs="",
            search_menu=_make_menu(qs="", counts={}, current=filter_name),
            result_sets=[],
        )

    engine = svcs.flask.container.get(SearchEngine)
    counts = _counts_by_name(engine, qs)
    result_sets = _result_sets(engine, qs, filter_name, counts)

    return render_template(
        "pages/search.j2",
        title="Rechercher",
        qs=qs,
        search_menu=_make_menu(qs=qs, counts=counts, current=filter_name),
        result_sets=result_sets,
    )


# ── Helpers ─────────────────────────────────────────────────────────


def _counts_by_name(engine: SearchEngine, qs: str) -> dict[str, int]:
    """Per-collection-name hit counts. The ``all`` entry is the sum."""
    counts: dict[str, int] = {}
    for collection in COLLECTIONS:
        type_name = collection["type"]
        if type_name is None:
            continue
        counts[collection["name"]] = engine.count(qs, type=type_name)
    counts["all"] = sum(counts.values())
    return counts


def _result_sets(
    engine: SearchEngine,
    qs: str,
    filter_name: str,
    counts: dict[str, int],
) -> list[ResultSet]:
    if filter_name == "all":
        named_types = [c for c in COLLECTIONS if c["type"] is not None]
    else:
        named_types = [c for c in COLLECTIONS if c["name"] == filter_name]

    out: list[ResultSet] = []
    for collection in named_types:
        type_name = collection["type"]
        if type_name is None:
            continue
        hits = engine.search(qs, type=type_name, limit=_DEFAULT_LIMIT)
        if not hits:
            continue
        out.append(
            ResultSet(
                name=collection["name"],
                label=collection["label"],
                icon=collection["icon"],
                count=counts.get(collection["name"], len(hits)),
                hits=[Hit.from_doc(doc) for doc in hits],
            )
        )
    return out


def _make_menu(
    *, qs: str, counts: dict[str, int], current: str
) -> list[dict]:
    return [
        {
            "name": c["name"],
            "label": c["label"],
            "icon": c["icon"],
            "href": url_for(".search", qs=qs, filter=c["name"]),
            "current": current == c["name"],
            "count": counts.get(c["name"], 0),
        }
        for c in COLLECTIONS
    ]


def _warn_if_semantic_requested() -> None:
    """The ``SEARCH_SEMANTIC=on`` switch is reserved for a future phase
    (vector field + HybridQuery). Until then, log once and fall through
    to the plain BM25 path so the page never silently misbehaves.
    """
    if current_app.config.get("SEARCH_SEMANTIC"):
        logger.warning(
            "SEARCH_SEMANTIC is set but vector indexing is not yet "
            "implemented; falling back to BM25-only ranking."
        )


# ── View models ─────────────────────────────────────────────────────


@dataclass(frozen=True)
class Hit:
    """Template-friendly view over a wesh hit document."""

    type: str
    title: str
    summary: str
    url: str
    timestamp: datetime | None

    @classmethod
    def from_doc(cls, doc: dict) -> Hit:
        return cls(
            type=doc.get("type", ""),
            title=doc.get("title", ""),
            summary=doc.get("summary", ""),
            url=doc.get("url", ""),
            timestamp=doc.get("timestamp"),
        )

    @property
    def date(self) -> arrow.Arrow | None:
        """Arrow handle exposing ``isoformat()``/``format()`` for Jinja."""
        if self.timestamp is None:
            return None
        return arrow.get(self.timestamp)


@dataclass(frozen=True)
class ResultSet:
    name: str
    label: str
    icon: str
    count: int
    hits: list[Hit] = field(default_factory=list)
