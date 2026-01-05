# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Copy/pasted.

TODO: Refactor.
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import Any, TypedDict

import webargs
from attr import define
from flask import request, url_for as url_for_orig
from jinja2 import Environment, FileSystemLoader, select_autoescape
from sqlalchemy import Select, false, func, nulls_last, or_, select
from webargs.flaskparser import parser

from app.flask.extensions import db
from app.flask.routing import url_for
from app.models.auth import User
from app.models.organisation import Organisation
from app.ui.labels import LABELS_ORGANISATION_TYPE
from app.ui.macros.icon import icon

__all__ = ["Column", "ColumnSpec", "Table"]


class ColumnSpec(TypedDict, total=False):
    """Type specification for column configuration dictionaries."""

    name: str
    label: str
    width: int
    align: str


@define
class Column:
    name: str
    label: str
    width: int = 0
    align: str = "left"

    @property
    def td_class(self) -> str:
        match self.align:
            case "right":
                return "text-right"
            case _:
                return ""


@define
class Table:
    records: list
    start = 0
    end = 10
    count = 20
    url_label = "Show"
    all_search = True
    searching = ""

    @property
    def columns(self):
        return list(self.compose())

    def compose(self) -> Iterable[Column]:
        """Override in subclasses to define columns via generator."""
        return self._columns()

    def _columns(self) -> list[Column]:
        return []

    @property
    def template(self):
        loader = FileSystemLoader(str(Path(__file__).parent))
        env = Environment(loader=loader, autoescape=select_autoescape())
        return env.get_template("table.html.j2")

    def render_cell(self, record: dict[str, Any], column: Column) -> str:
        renderer = getattr(self, f"render_{column.name}", None)
        if renderer:
            return renderer(record)
        return record.get(column.name, "")

    def render(self) -> str:
        ctx = {
            "records": self.records,
            "columns": self.columns,
            "render_cell": self.render_cell,
            "icon": icon,
            "start": self.start,
            "end": self.end,
            "count": self.count,
            "url_label": self.url_label,
            "all_search": self.all_search,
            "searching": self.searching,
        }
        return self.template.render(**ctx)


class DataSource:
    model_class: type | None = None
    search: str = ""
    limit: int = 15
    offset: int = 0

    def __init__(self, model_class=None) -> None:
        if model_class:
            self.model_class = model_class
        args = self.get_args()
        self.search = args["search"].lower()
        self.limit = args["limit"]
        self.offset = args["offset"]

    def get_args(self) -> dict[str, Any]:
        json_data_args = {
            "limit": webargs.fields.Int(load_default=15),
            "offset": webargs.fields.Int(load_default=0),
            "search": webargs.fields.Str(load_default=""),
        }
        return parser.parse(json_data_args, request, location="query")

    def count(self) -> int:
        assert self.model_class is not None
        stmt = select(func.count()).select_from(self.model_class)
        stmt = self.add_search_filter(stmt)
        return db.session.scalar(stmt) or 0

    def records(self):
        stmt = self.get_base_select()
        stmt = self.add_search_filter(stmt)
        objects = list(db.session.scalars(stmt))
        return self.make_records(objects)

    def get_base_select(self) -> Select:
        assert self.model_class is not None
        return select(self.model_class).offset(self.offset).limit(self.limit)

    def add_search_filter(self, stmt):
        return stmt

    def make_records(self, objects) -> list[dict]:
        # TODO: make a generic version
        return []


class GenericUserDataSource:
    """Data source for paginated user lists.

    State is parsed from request query parameters on each instantiation,
    ensuring thread-safety and proper isolation between requests/users.
    """

    DEFAULT_LIMIT = 12

    def __init__(self) -> None:
        """Parse pagination state from request query parameters."""
        self.search = request.args.get("search", "").lower()
        self.limit = request.args.get("limit", self.DEFAULT_LIMIT, type=int)
        self.offset = request.args.get("offset", 0, type=int)

    def next_offset(self) -> int:
        """Calculate offset for next page."""
        new_offset = self.offset + self.limit
        if new_offset < self.count():
            return new_offset
        return self.offset

    def prev_offset(self) -> int:
        """Calculate offset for previous page."""
        return max(0, self.offset - self.limit)

    def count(self) -> int:
        stmt = select(func.count()).select_from(User)
        stmt = stmt.filter(User.is_clone == false())
        stmt = self.add_search_filter(stmt)
        return db.session.scalar(stmt) or 0

    def records(self):
        stmt = self.get_base_select()
        stmt = self.add_search_filter(stmt)
        objects = list(db.session.scalars(stmt))
        return self.make_records(objects)

    def get_base_select(self) -> Select:
        return (
            select(User)
            .where(User.is_clone == false())
            .offset(self.offset)
            .limit(self.limit)
        )

    def add_search_filter(self, stmt):
        if self.search:
            stmt = stmt.filter(
                or_(
                    User.first_name.ilike(f"%{self.search}%"),
                    User.last_name.ilike(f"%{self.search}%"),
                    User.email.ilike(f"%{self.search}%"),
                    User.organisation.has(Organisation.name.ilike(f"%{self.search}%")),
                )
            )
        return stmt

    def make_records(self, objects) -> list[dict]:
        result = []
        for obj in objects:
            record = {
                "$url": url_for(obj),
                "id": obj.id,
                "show": url_for_orig(".show_user", uid=obj.id),
                "name": obj.full_name,
                "email": obj.email_safe_copy or obj.email,
                "job_title": obj.job_title,
                "organisation_name": obj.organisation_name,
                "status": obj.status,
                "karma": f"{obj.karma:0.1f}",
            }
            result.append(record)
        return result


class GenericOrgDataSource:
    """Data source for paginated organisation lists.

    State is parsed from request query parameters on each instantiation,
    ensuring thread-safety and proper isolation between requests/users.
    """

    DEFAULT_LIMIT = 12

    def __init__(self) -> None:
        """Parse pagination state from request query parameters."""
        self.search = request.args.get("search", "").lower()
        self.limit = request.args.get("limit", self.DEFAULT_LIMIT, type=int)
        self.offset = request.args.get("offset", 0, type=int)

    def next_offset(self) -> int:
        """Calculate offset for next page."""
        new_offset = self.offset + self.limit
        if new_offset < self.count():
            return new_offset
        return self.offset

    def prev_offset(self) -> int:
        """Calculate offset for previous page."""
        return max(0, self.offset - self.limit)

    def count(self) -> int:
        stmt = select(func.count()).select_from(Organisation)
        stmt = self.add_search_filter(stmt)
        return db.session.scalar(stmt) or 0

    def records(self):
        stmt = self.get_base_select()
        stmt = self.add_search_filter(stmt)
        objects = list(db.session.scalars(stmt))
        return self.make_records(objects)

    def get_base_select(self) -> Select:
        return (
            select(Organisation)
            .where(Organisation.deleted_at.is_(None))
            .order_by(nulls_last(Organisation.name))
            .offset(self.offset)
            .limit(self.limit)
        )

    def add_search_filter(self, stmt):
        if self.search:
            stmt = stmt.filter(Organisation.name.ilike(f"%{self.search}%"))
        return stmt

    def make_records(self, objects) -> list[dict]:
        result = []
        for obj in objects:
            record = {
                "$url": url_for(obj),
                "id": obj.id,
                "show": url_for_orig(".show_org", uid=obj.id),
                "name": obj.name,
                "karma": obj.karma,
                "type": LABELS_ORGANISATION_TYPE.get(obj.type, obj.type),
            }
            result.append(record)
        return result
