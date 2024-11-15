# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only
from __future__ import annotations

from flask import Response, request, url_for as url_for_orig
from sqlalchemy import desc, false, func, nulls_last, select, true

from app.flask.extensions import db
from app.flask.lib.pages import page
from app.flask.routing import url_for
from app.models.auth import User

from ..table import Column, GenericUserDataSource, Table
from .base import BaseAdminPage
from .home import AdminHomePage

TABLE_COLUMNS = [
    {"name": "email", "label": "E-mail", "width": 50},
    {"name": "karma", "label": "Perf.", "width": 50, "align": "right"},
    {"name": "name", "label": "Nom", "width": 50},
    {"name": "job_title", "label": "Job", "width": 50},
    {"name": "organisation_name", "label": "Org.", "width": 50},
    {"name": "status", "label": "Statut", "width": 50},
]


class UsersTable(Table):
    url_label = "Détail"
    all_search = False

    def compose(self):
        for col in TABLE_COLUMNS:
            yield Column(**col)


class UserDataSource(GenericUserDataSource):
    @classmethod
    def count(cls) -> int:
        stmt = select(func.count()).select_from(User)
        stmt = stmt.filter(
            User.active == true(),
            User.is_clone == false(),
            User.deleted_at.is_(None),
        )
        stmt = cls.add_search_filter(stmt)
        return db.session.scalar(stmt)

    @classmethod
    def get_base_select(cls) -> select:
        return (
            select(User)
            .where(
                User.active == true(),
                User.is_clone == false(),
                User.deleted_at.is_(None),
            )
            .order_by(nulls_last(desc(User.last_login_at)))
            .offset(cls.offset)
            .limit(cls.limit)
        )

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
                "email": obj.email_safe_copy or obj.email,
                "job_title": obj.job_title,
                "organisation_name": obj.organisation_name,
                "status": obj.status,
                "karma": f"{obj.karma:0.1f}",
            }
            result.append(record)
        return result


@page
class AdminUsersPage(BaseAdminPage):
    name = "users"
    label = "Utilisateurs"
    title = "Utilisateurs"
    icon = "users"

    template = "admin/pages/generic_table.j2"
    parent = AdminHomePage

    ds_class = UserDataSource
    table_class = UsersTable

    def context(self):
        records = self.ds_class.records()
        table = self.table_class(records)
        table.start = self.ds_class.offset + 1
        table.end = self.ds_class.offset + self.ds_class.limit
        count = self.ds_class.count()
        table.end = min(self.ds_class.offset + self.ds_class.limit, count)
        table.count = count
        table.searching = self.ds_class.search
        return {
            "table": table,
        }

    def hx_post(self) -> str | Response:
        action = request.form.get("action")
        search_string = request.form.get("search")
        if action:
            if action == "next":
                self.ds_class.inc()
                response = Response("")
                response.headers["HX-Redirect"] = self.url
                return response
            if action == "previous":
                self.ds_class.dec()
                response = Response("")
                response.headers["HX-Redirect"] = self.url
                return response
        if search_string:
            if search_string != self.ds_class.search:
                self.ds_class.first_page()
            self.ds_class.search = search_string
            response = Response("")
            response.headers["HX-Redirect"] = self.url
            return response
        else:
            if self.ds_class.search:
                self.ds_class.first_page()
            self.ds_class.search = ""
            response = Response("")
            response.headers["HX-Redirect"] = self.url
            return response

        # no validation
        response = Response("")
        response.headers["HX-Redirect"] = AdminHomePage().url
        return response
