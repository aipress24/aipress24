# Copyright (c) 2021-2024 - Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from app.flask.lib.pages import page
from app.models.auth import User

from .. import table as t
from .base import AdminListPage
from .home import AdminHomePage

# from app.modules.kyc.models import MembershipApplication


TABLE_COLUMNS = [
    {"name": "first_name", "label": "Prénom", "width": 50},
    {"name": "last_name", "label": "Nom", "width": 50},
]


class ApplicationsTable(t.Table):
    def compose(self):
        for col in TABLE_COLUMNS:
            yield t.Column(**col)


class ApplicationDataSource(t.DataSource):
    # model_class = MembershipApplication
    model_class = User

    def add_search_filter(self, stmt):
        if self.search:
            stmt = stmt.filter(User.last_name.ilike(f"{self.search}%"))
        return stmt

    def make_records(self, objects) -> list[dict]:
        result = []
        for obj in objects:
            data = obj.data or {}
            record = {
                "$url": "",
                "id": obj.id,
                "first_name": data.get("first_name", "Inconnu"),
                "last_name": data.get("last_name", "Inconnu"),
            }
            result.append(record)
        return result


@page
class AdminKycPage(AdminListPage):
    name = "kyc"
    label = "KYC"
    title = "KYC"
    icon = "clipboard-document-check"

    template = "admin/pages/generic_table.j2"
    parent = AdminHomePage

    ds_class = ApplicationDataSource
    table_class = ApplicationsTable


# @page
# class AdminKycPage(AdminPage):
#     name = "kyc"
#     label = "KYC"
#     title = "KYC"
#     icon = "users"
#
#     template = "admin/pages/generic_table.j2"
#     parent = AdminHomePage
#
#     ds_class = ApplicationDataSource
#     table_class = ApplicationsTable
