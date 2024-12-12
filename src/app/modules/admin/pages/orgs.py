# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from flask import Response, request

from app.flask.lib.pages import page

from ..table import Column, GenericOrgDataSource, Table
from .base import BaseAdminPage
from .home import AdminHomePage

TABLE_COLUMNS = [
    {"name": "name", "label": "Nom", "width": 50},
    {"name": "type", "label": "type", "width": 20},
    {"name": "karma", "label": "Réputation", "width": 8},
]


class OrgsTable(Table):
    url_label = "Détail"
    all_search = False

    def compose(self):
        for col in TABLE_COLUMNS:
            yield Column(**col)


class OrgDataSource(GenericOrgDataSource):
    pass


@page
class AdminOrgsPage(BaseAdminPage):
    name = "orgs"
    label = "Organisations"
    title = "Organisations"
    icon = "building-office"

    template = "admin/pages/generic_table.j2"
    parent = AdminHomePage

    ds_class = OrgDataSource
    table_class = OrgsTable

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
        # response = Response("")
        # response.headers["HX-Redirect"] = AdminHomePage().url
        # return response
