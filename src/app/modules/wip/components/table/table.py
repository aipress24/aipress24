# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

import inspect
import uuid
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import Any, ClassVar
from urllib.parse import urlencode

import attrs
from arrow import Arrow
from attr import define
from flask import current_app, request
from jinja2 import Environment, Template
from markupsafe import Markup

from app.flask.routing import url_for
from app.lib.names import to_snake_case

__all__ = []


class DataSource(ABC):
    offset: int
    limit: int

    @abstractmethod
    def get_items(self) -> list:
        raise NotImplementedError

    @abstractmethod
    def get_count(self) -> int:
        raise NotImplementedError


class Table:
    data_source: DataSource
    columns: ClassVar[list[dict[str, Any]]]

    def get_items(self):
        return self.data_source.get_items()

    def render(self, template_name="") -> str:
        if not template_name:
            rows = [Row(self, item) for item in self.get_items()]
            template = self.get_template()
            return Markup(template.render(rows=rows, table=self, url_for=self.url_for))
        template = self.get_template(template_name)
        return Markup(template.render(table=self))

    def url_for(self, object, _action="get", **kwargs):
        return url_for(object, **kwargs)

    @property
    def pagination(self):
        return Pagination(self)

    def get_actions(self, item):
        return []

    def get_template(self, name="") -> Template:
        if not name:
            name = "table.j2"
        return get_template(Table, name)

    def get_row_template(self) -> Template:
        return get_template(Table, "table_row.j2")


@define
class Row:
    table: Table
    item: Any

    cache: dict[str, Any] = attrs.Factory(dict)

    @property
    def id(self):
        if "id" in self.cache:
            return self.cache["id"]
        self.cache["id"] = uuid.uuid4().hex
        return self.cache["id"]

    def render(self) -> str:
        template = self.table.get_row_template()
        return Markup(
            template.render(row=self, item=self.item, url_for=self.table.url_for)
        )

    def get_cells(self):
        result = []
        for column in self.table.columns:
            if column["name"] == "$actions":
                continue
            cell = Cell(column, self.item)
            result.append(cell)
        return result

    def get_actions(self):
        return self.table.get_actions(self.item)


@define
class Cell:
    column: dict[str, Any]
    item: Any

    def render(self) -> str:
        value = getattr(self.item, self.column["name"])
        if "render" in self.column:
            return self.column["render"](self.item)
        match value:
            case True:
                return Markup('<i class="fas fa-check text-green-500"></i>')
            case False:
                return Markup('<i class="fas fa-times text-red-500"></i>')
            case datetime():
                return value.strftime("%d/%m/%Y à %H:%M")
            case Arrow():
                return value.strftime("%d/%m/%Y à %H:%M")
            case str():
                return value
            case _:
                return str(value)

    def __getitem__(self, item):
        if item == "class":
            return self.column.get("class", "")
        raise KeyError(item)


@define
class Pagination:
    table: Table

    def render(self) -> str:
        data_source = self.table.data_source
        total: int = data_source.get_count()

        if total == 0:
            return ""

        template = get_template(self, "table_pagination.j2")

        start = data_source.offset + 1
        end = min(data_source.offset + data_source.limit, total)
        current_page = (data_source.offset // data_source.limit) + 1
        total_pages = (total + data_source.limit - 1) // data_source.limit

        def get_url_for_page(page_num):
            offset = (page_num - 1) * data_source.limit
            args = request.args.copy()
            args["offset"] = str(offset)
            args["limit"] = str(data_source.limit)
            return f"{request.path}?{urlencode(args)}"

        links = []
        for i in range(1, total_pages + 1):
            links.append(
                {"page": i, "is_current": i == current_page, "url": get_url_for_page(i)}
            )

        ctx = {
            "total": total,
            "first": start,
            "last": end,
            "current_page": current_page,
            "total_pages": total_pages,
            "links": links,
            "has_prev": data_source.offset > 0,
            "prev_url": get_url_for_page(current_page - 1) if current_page > 1 else "#",
            "has_next": end < total,
            "next_url": get_url_for_page(current_page + 1) if end < total else "#",
        }
        return Markup(template.render(**ctx))


def get_template(parent: Any, name: str = "") -> Template:
    if not name:
        template_name = to_snake_case(parent.__name__) + ".j2"
    else:
        template_name = name

    match parent:
        case str():
            template_file = Path(parent)
        case type():
            template_file = Path(inspect.getfile(parent)).parent / template_name
        case object():
            template_file = (
                Path(inspect.getfile(parent.__class__)).parent / template_name
            )
        case _:
            msg = f"Invalid parent type: {type(parent)}"
            raise ValueError(msg)

    jinja_env: Environment = current_app.jinja_env
    return jinja_env.from_string(template_file.read_text())
