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
from app.modules.admin.table import Column, Table

from .base import BaseAdminPage
from .home import AdminHomePage
from .new_users import NewUserDataSource

TABLE_COLUMNS = [
    {"name": "name", "label": "Nom", "width": 50},
    {"name": "organisation_name", "label": "Org.", "width": 50},
    {"name": "last_login_at", "label": "Connexion", "width": 35},
    {"name": "job_title", "label": "Job", "width": 50},
    {"name": "email", "label": "E-mail", "width": 50},
]


class ModifUsersTable(Table):
    url_label = "Validation"
    all_search = False

    def compose(self):
        for col in TABLE_COLUMNS:
            yield Column(**col)


class ModifUserDataSource(NewUserDataSource):
    @classmethod
    def count(cls) -> int:
        stmt = select(func.count()).select_from(User)
        stmt = stmt.filter(
            User.active == false(),
            User.is_clone == true(),
            User.deleted_at.is_(None),
        )
        stmt = cls.add_search_filter(stmt)
        return db.session.scalar(stmt)

    @classmethod
    def get_base_select(cls) -> select:
        return (
            select(User)
            .where(
                User.active == false(),
                User.is_clone == true(),
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
                "show": url_for_orig(".validation_profile", uid=obj.id),
                "name": obj.full_name,
                "email": obj.email_safe_copy or obj.email,
                "organisation_name": obj.organisation_name,
                "last_login_at": obj.submited_at.strftime("%d %b %G %H:%M"),
            }
            result.append(record)
        return result


@page
class AdminModifUsersPage(BaseAdminPage):
    name = "modif_users"
    label = "Modifications"
    title = "Modifications de profils à valider"
    icon = "users"

    template = "admin/pages/generic_table.j2"
    parent = AdminHomePage

    ds_class = ModifUserDataSource
    table_class = ModifUsersTable

    def context(self):
        records = self.ds_class.records()
        table = self.table_class(records)
        table.start = self.ds_class.offset + 1
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
        if self.ds_class.search:
            self.ds_class.first_page()
        self.ds_class.search = ""
        response = Response("")
        response.headers["HX-Redirect"] = self.url
        return response

        # no validation
        # response = Response("")
        # response.headers["HX-Redirect"] = AdminHomePage().url
        # return response
