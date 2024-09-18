# Copyright (c) 2021-2024 - Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from flask import url_for as url_for_orig
from sqlalchemy import false, select

from app.flask.lib.pages import page
from app.flask.routing import url_for
from app.models.auth import User

from .. import table_no_all as t
from .base import AdminListNoAllPage
from .home import AdminHomePage

TABLE_COLUMNS = [
    {"name": "name", "label": "Nom", "width": 50},
    {"name": "organisation_name", "label": "Org.", "width": 50},
    {"name": "job_title", "label": "Job", "width": 50},
    {"name": "email", "label": "E-mail", "width": 50},
]


class NewUsersTable(t.TableNoAll):
    def compose(self):
        for col in TABLE_COLUMNS:
            yield t.Column(**col)


class NewUserDataSource(t.DataSource):
    model_class = User

    def get_base_select(self) -> select:
        return (
            select(User)
            .where(User.active == false(), User.is_clone == false())
            .offset(self.offset)
            .limit(self.limit)
        )

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
                "validation": url_for_orig(".validation_profile", uid=obj.id),
                "name": obj.full_name,
                "email": obj.email_backup or obj.email,
                "job_title": obj.job_title,
                "organisation_name": obj.profile.organisation_name,
            }
            result.append(record)
        return result


@page
class AdminNewUsersPage(AdminListNoAllPage):
    name = "new_users"
    label = "Inscriptions"
    title = "Utilisateurs à valider"
    icon = "users"

    template = "admin/pages/generic_table_no_all.j2"
    parent = AdminHomePage

    ds_class = NewUserDataSource
    table_class = NewUsersTable
