# Copyright (c) 2021-2024 - Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from app.flask.lib.pages import page
from app.flask.routing import url_for
from app.models.organisation import Organisation

from .. import table as t
from .base import AdminListPage
from .home import AdminHomePage

TABLE_COLUMNS = [
    {"name": "name", "label": "Nom", "width": 50},
    {"name": "num_members", "label": "# membres", "width": 50, "align": "right"},
    {"name": "status", "label": "Statut", "width": 50},
    {"name": "karma", "label": "Réput.", "width": 50, "align": "right"},
]


class OrgsTable(t.Table):
    def compose(self):
        for col in TABLE_COLUMNS:
            yield t.Column(**col)


class OrgDataSource(t.DataSource):
    model_class = Organisation

    def add_search_filter(self, stmt):
        if self.search:
            stmt = stmt.filter(Organisation.name.ilike(f"{self.search}%"))
        return stmt

    def make_records(self, objects) -> list[dict]:
        result = []
        for obj in objects:
            record = {
                "$url": url_for(obj),
                "id": obj.id,
                "name": obj.name,
                "num_members": 0,
                "karma": obj.karma,
            }
            result.append(record)
        return result


@page
class AdminOrgsPage(AdminListPage):
    name = "orgs"
    label = "Organisations"
    title = "Organisations"
    icon = "building-office"

    template = "admin/pages/generic_table.j2"
    parent = AdminHomePage

    ds_class = OrgDataSource
    table_class = OrgsTable

    #
    # # def context(self):
    # #     table = {
    # #         "columns": TABLE_COLUMNS,
    # #         "data_source": url_for(".groups__json_data"),
    # #     }
    # #     return {"table": table}
    #
    # def context(self):
    #     groups = self.get_data()
    #     table = OrgsTable(groups)
    #     return {"table": table}
    #
    # def get_data(self) -> list[dict]:
    #     stmt = select(Organisation).limit(20)
    #     objects: list[Organisation] = list(get_multi(Organisation, stmt))
    #     data = [
    #         {
    #             "$url": url_for(obj),
    #             "id": obj.id,
    #             "name": obj.name,
    #             "num_members": 0,
    #             "karma": obj.karma,
    #         }
    #         for obj in objects
    #     ]
    #     return data
    #
    # @expose
    # def json_data(self):
    #     args = parser.parse(json_data_args, request, location="query")
    #     search = args["search"].lower()
    #
    #     stmt = select(func.count()).select_from(Organisation)
    #
    #     if search:
    #         stmt = stmt.filter(Organisation.name.ilike(f"{search}%"))
    #     total: int = db.session.scalar(stmt)
    #
    #     stmt = select(Organisation).offset(args["offset"]).limit(args["limit"])
    #     if search:
    #         stmt = stmt.filter(Organisation.name.ilike(f"{search}%"))
    #     objects: list[Organisation] = list(get_multi(Organisation, stmt))
    #
    #     data = [
    #         {
    #             "$url": url_for(obj),
    #             "id": obj.id,
    #             "name": obj.name,
    #             "num_members": obj.num_members,
    #             "status": obj.status,
    #             "karma": obj.karma,
    #         }
    #         for obj in objects
    #     ]
    #     return jsonify(data=data, total=total)
