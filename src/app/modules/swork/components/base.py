# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

import re
from typing import ClassVar

from sqlalchemy.sql import Select

from app.flask.lib.pywire import WiredComponent
from app.models.mixins import Addressable


class BaseList(WiredComponent):
    search: str = ""
    filter_states: dict

    filters: ClassVar[list[Filter]] = []

    _attrs: ClassVar = ["search", "filter_states"]

    def __init__(self, id=None) -> None:
        super().__init__(id)
        self.filter_states = {}
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

    def get_base_statement(self) -> Select:
        raise NotImplementedError

    def apply_search(self, stmt):
        search = self.search.strip()
        if not search:
            return stmt

        m = re.search(r"([0-9][0-9][0-9][0-9][0-9])", search)
        if m:
            zip_code = m.group(1)
            search = search.replace(zip_code, "").strip()
            stmt = stmt.where(Addressable.zip_code == zip_code)

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
            options = sorted({selector(obj) for obj in objects})
            self.options = [opt for opt in options if opt]
        elif isinstance(selector, str):
            self.options = sorted({getattr(o, selector) for o in objects})
        else:
            msg = f"Invalid selector: {selector}"
            raise TypeError(msg)

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
        if isinstance(obj, Addressable):
            return str(obj.city)
        return ""

    def apply(self, stmt, state):
        active_options = self.active_options(state)
        if active_options:
            return stmt.where(Addressable.city.in_(active_options))
        return stmt


class FilterByDept(Filter):
    id = "dept"
    label = "Département"

    def selector(self, obj) -> str:
        if isinstance(obj, Addressable):
            return str(obj.dept_code)
        return ""

    def apply(self, stmt, state):
        active_options = self.active_options(state)
        if active_options:
            return stmt.where(Addressable.dept_code.in_(active_options))
        return stmt
