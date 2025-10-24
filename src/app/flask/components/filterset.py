# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

import pipe as p
from flask import session


class FilterSet:
    filter_specs: list
    filters: list

    def __init__(self, filter_specs) -> None:
        self.filter_specs = filter_specs
        self.filters = []

    def init(self, objects) -> None:
        for spec in self.filter_specs:
            id = spec["id"]
            label = spec["label"]
            options = spec.get("options")
            filter = Filter(id, label)
            filter.init(objects, options=options)
            self.filters.append(filter)

    def get_filters(self):
        result = []
        for filter in self.filters:
            result.append(
                {
                    "id": filter.name,
                    "label": filter.label,
                    "options": filter.options,
                }
            )
        return result


class Filter:
    name: str
    label: str
    options: list

    def __init__(self, name: str, label: str) -> None:
        self.name = name
        self.label = label
        self.options = []

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} {self.name} {self.label}>"

    def init(self, objects, options=None) -> None:
        if options is not None:
            for option in options:
                self.options.append(
                    {
                        "id": option,
                        "label": option,
                    }
                )
            return

        def getter(obj):
            return getattr(obj, self.name)

        options = list(objects | p.map(getter) | p.sort | p.dedup)
        for option in options:
            self.options.append(
                {
                    "id": option,
                    "label": option,
                }
            )


class Sorter:
    def __init__(self, options) -> None:
        self.options = []
        for option in options:
            self.options.append(
                {
                    "id": f"sort:{option[0]}",
                    "label": option[1],
                }
            )

    @property
    def current(self):
        sort_order = session.get("wire:sort-order", "date")
        for option in self.options:
            if option["id"] == f"sort:{sort_order}":
                return option["label"]
        return "Date (default)"
