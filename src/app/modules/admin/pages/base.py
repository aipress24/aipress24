# Copyright (c) 2021-2024 - Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

import abc

from app.flask.lib.pages import Page

from .. import table as t


class BaseAdminPage(Page, abc.ABC):
    icon: str
    label: str

    def menus(self):
        # Lazy import to prevent circular import
        from .menu import make_menu

        name = self.name
        return {
            "secondary": make_menu(name),
        }


class AdminListPage(BaseAdminPage):
    ds_class: type[t.DataSource]
    table_class: type[t.Table]

    def context(self):
        ds = self.ds_class()
        records = ds.records()
        table = self.table_class(records)
        return {"table": table}
