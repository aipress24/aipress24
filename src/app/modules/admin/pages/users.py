# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only
from __future__ import annotations

from urllib.parse import urlencode

from flask import Response, request, url_for as url_for_orig
from sqlalchemy import Select, desc, false, func, nulls_last, select, true

from app.flask.extensions import db
from app.flask.lib.pages import page
from app.flask.routing import url_for
from app.models.auth import User
from app.modules.admin.table import Column, GenericUserDataSource, Table

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
    def count(self) -> int:
        stmt = select(func.count()).select_from(User)
        stmt = stmt.filter(
            User.active == true(),
            User.is_clone == false(),
            User.deleted_at.is_(None),
        )
        stmt = self.add_search_filter(stmt)
        return db.session.scalar(stmt) or 0

    def get_base_select(self) -> Select:
        return (
            select(User)
            .where(
                User.active == true(),
                User.is_clone == false(),
                User.deleted_at.is_(None),
            )
            .order_by(nulls_last(desc(User.last_login_at)))
            .offset(self.offset)
            .limit(self.limit)
        )

    def make_records(self, objects) -> list[dict]:
        result = []
        for obj in objects:
            record = {
                "$url": url_for(obj),
                "id": obj.id,
                "show": url_for_orig(".show_profile", uid=obj.id),
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

    def _build_url(self, offset: int = 0, search: str = "") -> str:
        """Build URL with pagination query parameters."""
        params: dict[str, int | str] = {}
        if offset > 0:
            params["offset"] = offset
        if search:
            params["search"] = search
        if params:
            return f"{self.url}?{urlencode(params)}"
        return self.url

    def context(self):
        ds = self.ds_class()
        records = ds.records()
        table = self.table_class(records)
        table.start = ds.offset + 1
        table.end = ds.offset + ds.limit
        count = ds.count()
        table.end = min(ds.offset + ds.limit, count)
        table.count = count
        table.searching = ds.search
        return {
            "table": table,
        }

    def hx_post(self) -> str | Response:
        ds = self.ds_class()
        action = request.form.get("action")
        search_string = request.form.get("search", "")

        if action == "next":
            redirect_url = self._build_url(offset=ds.next_offset(), search=ds.search)
            response = Response("")
            response.headers["HX-Redirect"] = redirect_url
            return response

        if action == "previous":
            redirect_url = self._build_url(offset=ds.prev_offset(), search=ds.search)
            response = Response("")
            response.headers["HX-Redirect"] = redirect_url
            return response

        # Search handling
        if search_string:
            # New search resets to first page
            offset = 0 if search_string != ds.search else ds.offset
            redirect_url = self._build_url(offset=offset, search=search_string)
        else:
            # Clear search, reset to first page
            redirect_url = self._build_url()

        response = Response("")
        response.headers["HX-Redirect"] = redirect_url
        return response
