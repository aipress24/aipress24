# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from json import JSONDecodeError, dumps, loads

import sqlalchemy as sa
from flask import request, session
from werkzeug.exceptions import BadRequest

from app.flask.components.filterset import FilterSet
from app.flask.sqla import get_multi
from app.models.lifecycle import PublicationStatus
from app.modules.wire.models import ArticlePost

FILTER_SPECS = [
    {
        "id": "sector",
        "label": "Secteur",
        "selector": "sector",
    },
    {
        "id": "topic",
        "label": "Rubrique",
        "selector": "topic",
    },
    {
        "id": "genre",
        "label": "Genre",
        "selector": "genre",
    },
    {
        "id": "section",
        "label": "Thématique",
        "selector": "section",
    },
    # {
    #     "id": "type_presse",
    #     "label": "Type de presse",
    #     "options": [
    #         "Nationale",
    #         "PQR",
    #         "Hebdo",
    #         "Mensuelle",
    #         "TV",
    #         "Radio",
    #         "Web",
    #         "Spécialisée",
    #     ],
    # },
    # {
    #     "id": "location",
    #     "label": "Localisation",
    #     "options": ["France", "Europe", "USA", "Chine", "..."],
    # },
]

SORTER_OPTIONS = [
    ("date", "Date"),
    ("views", "Popularité (vues)"),
    ("likes", "Popularité (likes)"),
    ("shares", "Popularité (partages)"),
    ("sales", "Ventes"),
]


class FilterBar:
    def __init__(self, tab: str = "wall") -> None:
        self.tab = tab
        self.state = self.get_state()
        self.filters = self.get_filters()

    #
    # Accessors
    #
    @property
    def active_filters(self):
        return [
            {
                "type": "selector",
                "id": filter["id"],
                "value": filter["value"],
                "label": filter["value"],
            }
            for filter in self.state.get("filters", [])
        ]

    @property
    def tag(self) -> str:
        filters = self.state.get("filters", [])
        for filter in filters:
            if filter["id"] == "tag":
                return filter["value"]
        return ""

    @property
    def sorter(self):
        return {
            "options": [
                {
                    "value": opt[0],
                    "label": opt[1],
                    "selected": opt[0] == self.state.get("sort-by", "date"),
                }
                for opt in SORTER_OPTIONS
            ],
        }

    @property
    def sort_order(self):
        return self.state.get("sort-by", "date")

    #
    # State management
    #
    def get_state(self):
        try:
            state_json = session[f"wire:{self.tab}:state"]
        except (JSONDecodeError, KeyError):
            return {}
        else:
            return loads(state_json)

    def save_state(self) -> None:
        session[f"wire:{self.tab}:state"] = dumps(self.state)

    def reset(self) -> None:
        self.state = {}
        self.save_state()

    def set_tag(self, value) -> None:
        self.add_filter("tag", value)
        self.save_state()

    def update_state(self) -> None:
        form = request.form
        action = form["action"]
        form_value = form["value"]
        form_id = form["id"]

        if action == "toggle":
            self.toggle_filter(form_id, form_value)
        elif action == "remove":
            self.remove_filter(form_id, form_value)
        elif action == "sort-by":
            self.sort_by(form_value)
        else:
            raise BadRequest

        self.save_state()

    def toggle_filter(self, id: str, value: str) -> None:
        if self.has_filter(id, value):
            self.remove_filter(id, value)
        else:
            self.add_filter(id, value)

    def has_filter(self, id: str, value: str):
        filters = self.state.get("filters", [])
        return any(
            filter["id"] == id and filter["value"] == value for filter in filters
        )

    def remove_filter(self, id, value) -> None:
        filters = self.state.get("filters", [])
        for i, filter in enumerate(filters):
            if filter["id"] == id and filter["value"] == value:
                del filters[i]
                break

    def add_filter(self, id, value) -> None:
        filters = self.state.get("filters", [])
        filters.append(
            {
                "id": id,
                "value": value,
            }
        )
        self.state["filters"] = filters

    def sort_by(self, value) -> None:
        self.state["sort-by"] = value

    #
    # Filtering
    #
    def get_filters(self):
        if self.tab == "com":
            return self.get_filters_for_com()
        return self.get_filters_for_articles()

    def get_filters_for_articles(self):
        stmt = sa.select(ArticlePost).where(
            ArticlePost.status == PublicationStatus.PUBLIC
        )
        articles = get_multi(ArticlePost, stmt)

        filter_set = FilterSet(FILTER_SPECS)
        filter_set.init(articles)

        return filter_set.get_filters()

    def get_filters_for_com(self):
        return []
        # stmt = sa.select(PressRelease).where(
        #     PressRelease.status == PublicationStatus.PUBLIC
        # )
        # press_releases = get_multi(PressRelease, stmt)
        #
        # filter_set = FilterSet(FILTER_SPECS)
        # filter_set.init(press_releases)
        #
        # return filter_set.get_filters()
