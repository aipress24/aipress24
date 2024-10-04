# Copyright (c) 2021-2024 - Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Copy/pasted.

TODO: Refactor.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import webargs
from attr import define
from flask import request
from flask import url_for as url_for_orig
from jinja2 import Environment, FileSystemLoader, select_autoescape
from sqlalchemy import false, func, or_, select
from webargs.flaskparser import parser

from app.flask.extensions import db
from app.flask.routing import url_for
from app.models.auth import KYCProfile, User
from app.ui.macros.icon import icon

__all__ = ["Column", "Table"]


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
        if hasattr(self, "compose"):
            return list(self.compose())
        else:
            return self._columns()

    def _columns(self):
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
        else:
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

    def __init__(self, model_class=None):
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
        stmt = select(func.count()).select_from(self.model_class)
        stmt = self.add_search_filter(stmt)
        return db.session.scalar(stmt)

    def records(self):
        stmt = self.get_base_select()
        stmt = self.add_search_filter(stmt)
        objects = list(db.session.scalars(stmt))
        return self.make_records(objects)

    def get_base_select(self) -> select:
        return select(self.model_class).offset(self.offset).limit(self.limit)

    def add_search_filter(self, stmt):
        return stmt

    def make_records(self, objects) -> list[dict]:
        # TODO: make a generic version
        return []


class GenericUserDataSource:
    search: str = ""
    limit: int = 12
    offset: int = 0

    @classmethod
    def inc(cls):
        new_offset = cls.offset + cls.limit
        if new_offset < cls.count():
            cls.offset = new_offset

    @classmethod
    def dec(cls):
        cls.offset = max(0, cls.offset - cls.limit)

    @classmethod
    def first_page(cls):
        cls.offset = 0

    @classmethod
    def count(cls) -> int:
        stmt = select(func.count()).select_from(User)
        stmt = stmt.filter(User.is_clone == false())
        stmt = cls.add_search_filter(stmt)
        return db.session.scalar(stmt)

    @classmethod
    def records(cls):
        stmt = cls.get_base_select()
        stmt = cls.add_search_filter(stmt)
        objects = list(db.session.scalars(stmt))
        return cls.make_records(objects)

    @classmethod
    def get_base_select(cls) -> select:
        return (
            select(User)
            .where(User.is_clone == false())
            .offset(cls.offset)
            .limit(cls.limit)
        )

    @classmethod
    def add_search_filter(cls, stmt):
        if cls.search:
            stmt = stmt.filter(
                or_(
                    User.first_name.ilike(f"%{cls.search}%"),
                    User.last_name.ilike(f"%{cls.search}%"),
                    User.email.ilike(f"%{cls.search}%"),
                    User.profile.has(
                        KYCProfile.organisation_name.ilike(f"%{cls.search}%")
                    ),
                )
            )
        return stmt

    @classmethod
    def make_records(cls, objects) -> list[dict]:
        result = []
        for obj in objects:
            record = {
                "$url": url_for(obj),  # strange, obj like a str?
                "id": obj.id,
                "show": url_for_orig(".show_profile", uid=obj.id),
                # "username": obj.username,
                "name": obj.full_name,
                "email": obj.email_backup or obj.email,
                "job_title": obj.job_title,
                "organisation_name": obj.profile.organisation_name,
                "status": obj.status,
                "karma": f"{obj.karma:0.1f}",
            }
            result.append(record)
        return result
