# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

import re
from abc import abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, ClassVar

from sqlalchemy.sql import Select

if TYPE_CHECKING:
    from sqlalchemy.sql.elements import ColumnElement

from app.flask.lib.pywire import WiredComponent
from app.models.mixins import Addressable


class BaseList(WiredComponent):
    search: str = ""
    filter_states: dict

    filters: ClassVar[list[Filter]] = []

    _attrs: ClassVar = ["search", "filter_states"]

    def __init__(self, id=None) -> None:
        super().__init__(id or "")
        self.filter_states = {}
        self.init_filter_states()

    def init_filter_states(self) -> None:
        self.filters = self.get_filters()  # type: ignore[misc]
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

    def apply_search(self, stmt: Select) -> Select:
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

    @abstractmethod
    def search_clause(self, search: str) -> ColumnElement[bool]:
        """Return a SQLAlchemy filter clause for the search term."""
        ...

    def get_filters(self) -> list[Filter]:
        return []

    def apply_filters(self, stmt: Select) -> Select:
        for filter in self.filters:
            state = self.filter_states[filter.id]
            stmt = filter.apply(stmt, state)

        return stmt

    def get_active_filters(self) -> list[dict[str, str | FilterOption]]:
        active_filters: list[dict[str, str | FilterOption]] = []
        for filter in self.filters:
            state = self.filter_states[filter.id]
            for i, option_value in enumerate(filter.options):
                if state.get(str(i)):
                    active_filters.append(
                        {
                            "filter_id": filter.id,
                            "filter_label": filter.label,
                            "option_value": option_value,
                        }
                    )
        return active_filters

    def action_apply_filters(self) -> None:
        """Triggered by wire:click on checkboxes to refresh the component."""
        # the component will rerender after method call

    def action_remove_filter(self, filter_id: str, option_value: str) -> None:
        if filter_id in self.filter_states:
            filter_obj = next((f for f in self.filters if f.id == filter_id), None)
            if filter_obj:
                found_index = -1
                for i, opt in enumerate(filter_obj.options):
                    if str(opt) == option_value:
                        found_index = i
                        break
                if found_index != -1:
                    self.filter_states[filter_id][str(found_index)] = False


@dataclass(frozen=True, order=True)
class FilterOption:
    """Class to replace simple option strings in Filter when a code is also required."""

    option: str
    code: str = field(default="", compare=False)

    def __str__(self) -> str:
        return self.option


class Filter:
    id: str
    label: str
    options: list[str | FilterOption] = []

    def __init__(self, objects: list[Any] | None = None) -> None:
        # Only initialize if no class-level options defined
        if not hasattr(self, "options") or self.options is Filter.options:
            self.options = []
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

    def apply(self, stmt: Select, state: dict[str, bool]) -> Select:
        """Apply this filter to the statement. Override in subclasses."""
        raise NotImplementedError

    def active_options(self, state: dict[str, bool]) -> list[str | FilterOption]:
        options: list[str | FilterOption] = []
        for i in range(len(state)):
            if state[str(i)]:
                options.append(self.options[i])
        return options


class FilterByCity(Filter):
    id = "city"
    label = "Ville"

    def selector(self, obj: Any) -> str:
        if isinstance(obj, Addressable):
            return str(obj.city)
        return ""

    def apply(self, stmt: Select, state: dict[str, bool]) -> Select:
        active_options = self.active_options(state)
        if active_options:
            return stmt.where(Addressable.city.in_(active_options))
        return stmt


class FilterByDept(Filter):
    id = "dept"
    label = "Département"

    def selector(self, obj: Any) -> str:
        if isinstance(obj, Addressable):
            return str(obj.dept_code)
        return ""

    def apply(self, stmt: Select, state: dict[str, bool]) -> Select:
        active_options = self.active_options(state)
        if active_options:
            return stmt.where(Addressable.dept_code.in_(active_options))
        return stmt
