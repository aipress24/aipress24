# Copyright (c) 2021-2024 - Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from flask import url_for as url_for_orig

from app.flask.lib.pages import page
from app.flask.routing import url_for
from app.models.auth import User

from .. import table as t
from .base import AdminListPage
from .home import AdminHomePage

TABLE_COLUMNS = [
    {"name": "email", "label": "E-mail", "width": 50},
    {"name": "karma", "label": "Perf.", "width": 50, "align": "right"},
    {"name": "name", "label": "Nom", "width": 50},
    {"name": "job_title", "label": "Job", "width": 50},
    {"name": "organisation_name", "label": "Org.", "width": 50},
    {"name": "status", "label": "Statut", "width": 50},
]


class UsersTable(t.Table):
    def compose(self):
        for col in TABLE_COLUMNS:
            yield t.Column(**col)


class UserDataSource(t.DataSource):
    model_class = User

    def add_search_filter(self, stmt):
        if self.search:
            stmt = stmt.filter(User.last_name.ilike(f"{self.search}%"))
        return stmt

    def make_records(self, objects) -> list[dict]:
        result = []
        for obj in objects:
            record = {
                "$url": url_for(obj),  # strange, obj like a str?
                "id": obj.id,
                "show": url_for_orig(".show_profile", uid=obj.id),
                # "username": obj.username,
                "name": obj.full_name,
                "email": obj.email,
                "job_title": obj.job_title,
                "organisation_name": obj.profile.organisation_name,
                "status": obj.status,
                "karma": f"{obj.karma:0.1f}",
            }
            result.append(record)
        return result


@page
class AdminUsersPage(AdminListPage):
    name = "users"
    label = "Utilisateurs"
    title = "Utilisateurs"
    icon = "users"

    template = "admin/pages/generic_table.j2"
    parent = AdminHomePage

    ds_class = UserDataSource
    table_class = UsersTable
