# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Admin users views."""

from __future__ import annotations

from flask import render_template
from flask.views import MethodView

from app.flask.lib.nav import nav
from app.modules.admin import blueprint

from ._common import build_table_context, handle_table_post


class UsersView(MethodView):
    """Users list page."""

    decorators = [nav(parent="index", icon="users", label="Utilisateurs")]

    def get(self):
        from ._users import UserDataSource, UsersTable

        ctx = build_table_context(UserDataSource, UsersTable)
        return render_template(
            "admin/pages/generic_table.j2",
            title="Utilisateurs",
            **ctx,
        )

    def post(self):
        from ._users import UserDataSource

        return handle_table_post(UserDataSource, "admin.users")


class NewUsersView(MethodView):
    """New users to validate page."""

    decorators = [nav(parent="index", icon="user-plus", label="Inscriptions")]

    def get(self):
        from ._new_users import NewUserDataSource, NewUsersTable

        ctx = build_table_context(NewUserDataSource, NewUsersTable)
        return render_template(
            "admin/pages/generic_table.j2",
            title="Nouveaux utilisateurs à valider",
            **ctx,
        )

    def post(self):
        from ._new_users import NewUserDataSource

        return handle_table_post(NewUserDataSource, "admin.new_users")


class ModifUsersView(MethodView):
    """Modified users to validate page."""

    decorators = [nav(parent="index", icon="user-cog", label="Modifications")]

    def get(self):
        from ._modif_users import ModifUserDataSource, ModifUsersTable

        ctx = build_table_context(ModifUserDataSource, ModifUsersTable)
        return render_template(
            "admin/pages/generic_table.j2",
            title="Modifications de profils à valider",
            **ctx,
        )

    def post(self):
        from ._modif_users import ModifUserDataSource

        return handle_table_post(ModifUserDataSource, "admin.modif_users")


# Register the views
blueprint.add_url_rule("/users", view_func=UsersView.as_view("users"))
blueprint.add_url_rule("/new_users", view_func=NewUsersView.as_view("new_users"))
blueprint.add_url_rule("/modif_users", view_func=ModifUsersView.as_view("modif_users"))
