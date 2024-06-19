# Copyright (c) 2021-2024 - Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from dataclasses import dataclass, field

import arrow
from flask import request

from app.flask.lib.pages import Page, page
from app.flask.routing import url_for

from ..backend import SearchBackend
from ..constants import COLLECTIONS

backend = SearchBackend()


@page
class SearchPage(Page):
    name = "search"
    label = "Rechercher"
    path = "/"
    template = "pages/search.j2"

    def context(self):
        qs = request.args.get("qs", "")
        filter = request.args.get("filter", "all")

        results = SearchResults(qs, filter)

        return {
            "qs": qs,
            "search_menu": results.make_menu(),
            "result_sets": results.get_active_sets(),
        }


@dataclass(frozen=True)
class SearchResults:
    qs: str
    filter: str
    results: list = field(default_factory=list)
    result_sets: list[ResultSet] = field(default_factory=list)

    def __post_init__(self):
        for collection in COLLECTIONS:
            cls = collection["class"]
            if not cls:
                continue
            assert isinstance(cls, type)

            search_parameters = {
                "q": self.qs,
                "query_by": "text",
                "facet_by": "tags",
                # 'filter_by': 'publication_year:<1998',
                "sort_by": "timestamp:desc",
                "exclude_fields": "text",
            }
            result_set = ResultSet(collection, search_parameters)
            self.result_sets.append(result_set)

    def make_menu(self):
        menu = []
        for collection in COLLECTIONS:
            name = collection["name"]
            label = collection["label"]
            icon = collection["icon"]

            if name == "all":
                count = sum(r.count for r in self.result_sets)
            else:
                count = sum(r.count for r in self.result_sets if r.name == name)

            entry = {
                "name": name,
                "label": label,
                "icon": icon,
                "href": url_for(".search", qs=self.qs, filter=name),
                "current": self.filter == name,
                "count": count,
            }
            menu.append(entry)

        return menu

    def get_active_sets(self):
        match self.filter:
            case "all":
                active_sets = [r for r in self.result_sets if r.count > 0]
            case _:
                active_sets = [r for r in self.result_sets if r.name == self.filter]
        return active_sets


class ResultSet:
    cls: type
    qs: str

    name: str
    label: str
    icon: str

    count: int = 0
    hits: list = field(default_factory=list)

    def __init__(self, collection, search_parameters):
        self.name = collection["name"]
        self.label = collection["label"]
        self.icon = collection["icon"]

        result = backend.get_collection(self.name).documents.search(search_parameters)
        # debug(result["facet_counts"])
        # debug(glom(result, ("hits", ["document.tags"])))
        self.count = result["found"]
        self.hits = [Hit(hit) for hit in result["hits"]]


@dataclass
class Hit:
    _hit: dict

    @property
    def title(self):
        return self._hit["document"]["title"]

    @property
    def summary(self):
        return self._hit["document"]["summary"]

    @property
    def date(self):
        return arrow.get(self._hit["document"]["timestamp"])

    @property
    def url(self):
        return self._hit["document"]["url"]
