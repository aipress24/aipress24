# Copyright (c) 2021-2024 - Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from sqlalchemy import false, select, true

from app.flask.lib.pages import page
from app.models.auth import User

from .base import AdminListNoAllPage
from .home import AdminHomePage
from .new_users import NewUserDataSource, NewUsersTable


class ModifUserDataSource(NewUserDataSource):
    model_class = User

    def get_base_select(self) -> select:
        return (
            select(User)
            .where(User.active == false(), User.is_clone == true())
            .offset(self.offset)
            .limit(self.limit)
        )


@page
class AdminModifUsersPage(AdminListNoAllPage):
    name = "modif_users"
    label = "Modifications"
    title = "Utilisateurs à valider"
    icon = "users"

    template = "admin/pages/generic_table_no_all.j2"
    parent = AdminHomePage

    ds_class = ModifUserDataSource
    table_class = NewUsersTable
