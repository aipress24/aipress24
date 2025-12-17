# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from urllib.parse import urlencode

from flask import Response, request

from app.flask.lib.pages import page
from app.modules.admin.table import Column, GenericOrgDataSource, Table

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
    icon = "building"

    template = "admin/pages/generic_table.j2"
    parent = AdminHomePage

    ds_class = OrgDataSource
    table_class = OrgsTable

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
