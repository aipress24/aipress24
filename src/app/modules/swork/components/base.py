# Copyright (c) 2021-2024 - Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

import re

from sqlalchemy.sql import Select

from app.flask.lib.pywire import WiredComponent
from app.models.geoloc import GeoLocation


class BaseList(WiredComponent):
    search: str = ""
    filter_states: dict = {}

    filters: list[Filter] = []

    _attrs = ["search", "filter_states"]

    def __init__(self, id=None) -> None:
        super().__init__(id)
        self.init_filter_states()

    def init_filter_states(self) -> None:
        self.filters = self.get_filters()
        for filter in self.filters:
            filter_id = filter.id
            if filter_id not in self.filter_states:
                self.filter_states[filter_id] = {
                    str(i): False for i in range(len(filter.options))
                }

    def make_stmt(self) -> Select:
        stmt = self.get_base_statement()
        stmt = self.apply_search(stmt)
        stmt = self.apply_filters(stmt)
        return stmt

    def get_base_statement(self):
        raise NotImplementedError

    def apply_search(self, stmt):
        search = self.search.strip()
        if not search:
            return stmt

        m = re.search("([0-9][0-9][0-9][0-9][0-9])", search)
        if m:
            postal_code = m.group(1)
            search = search.replace(postal_code, "").strip()
            stmt = stmt.where(GeoLocation.postal_code == postal_code)

        if search:
            stmt = stmt.where(self.search_clause(search))

        return stmt

    def search_clause(self, search: str):
        raise NotImplementedError

    def get_filters(self):
        return []

    def apply_filters(self, stmt):
        for filter in self.filters:
            state = self.filter_states[filter.id]
            stmt = filter.apply(stmt, state)

        return stmt


class Filter:
    id: str
    label: str
    options: list[str]

    def __init__(self, objects: list | None = None) -> None:
        if not objects:
            return

        if (selector := getattr(self, "selector", None)) is None:
            return

        if callable(selector):
            self.options = sorted({selector(obj) for obj in objects})
        elif isinstance(selector, str):
            self.options = sorted({getattr(o, selector) for o in objects})
        else:
            raise TypeError(f"Invalid selector: {selector}")

    def apply(self, stmt, state):
        raise NotImplementedError

    def active_options(self, state):
        options = []
        for i in range(len(state)):
            if state[str(i)]:
                options.append(self.options[i])
        return options


class FilterByCity(Filter):
    id = "city"
    label = "Ville"

    def selector(self, obj) -> str:
        if obj.geoloc:
            return obj.geoloc.city_name
        return ""

    def apply(self, stmt, state):
        active_options = self.active_options(state)
        if active_options:
            return stmt.where(GeoLocation.city_name.in_(active_options))
        return stmt


class FilterByDept(Filter):
    id = "dept"
    label = "Département"

    def selector(self, obj) -> str:
        if obj.geoloc:
            return obj.geoloc.dept_code
        return ""

    def apply(self, stmt, state):
        active_options = self.active_options(state)
        if active_options:
            return stmt.where(GeoLocation.dept_code.in_(active_options))
        return stmt
