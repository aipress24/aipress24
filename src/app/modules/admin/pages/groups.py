# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from app.modules.admin.views._groups import GroupDataSource, GroupsTable

from .base import AdminListPage
from .home import AdminHomePage


# Note: Route now handled by views/groups.py
class AdminGroupsPage(AdminListPage):
    name = "groups"
    label = "Groupes"
    title = "Groupes"
    icon = "user-group"

    template = "admin/pages/generic_table.j2"
    parent = AdminHomePage

    ds_class = GroupDataSource
    table_class = GroupsTable
