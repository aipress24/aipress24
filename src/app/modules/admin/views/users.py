# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Admin users views."""

from __future__ import annotations

from flask import render_template

from app.flask.lib.nav import nav
from app.modules.admin import blueprint

from ._common import build_table_context, handle_table_post


@blueprint.route("/users")
@nav(parent="index", icon="users", label="Utilisateurs")
def users():
    """Users list page."""
    from app.modules.admin.pages.users import UserDataSource, UsersTable

    ctx = build_table_context(UserDataSource, UsersTable)
    return render_template(
        "admin/pages/generic_table.j2",
        title="Utilisateurs",
        **ctx,
    )


@blueprint.route("/users", methods=["POST"])
@nav(hidden=True)
def users_post():
    """Handle users pagination/search."""
    from app.modules.admin.pages.users import UserDataSource

    return handle_table_post(UserDataSource, "admin.users")


@blueprint.route("/new_users")
@nav(parent="index", icon="user-plus", label="Inscriptions")
def new_users():
    """New users to validate page."""
    from app.modules.admin.pages.new_users import NewUserDataSource, NewUsersTable

    ctx = build_table_context(NewUserDataSource, NewUsersTable)
    return render_template(
        "admin/pages/generic_table.j2",
        title="Nouveaux utilisateurs à valider",
        **ctx,
    )


@blueprint.route("/new_users", methods=["POST"])
@nav(hidden=True)
def new_users_post():
    """Handle new users pagination/search."""
    from app.modules.admin.pages.new_users import NewUserDataSource

    return handle_table_post(NewUserDataSource, "admin.new_users")


@blueprint.route("/modif_users")
@nav(parent="index", icon="user-cog", label="Modifications")
def modif_users():
    """Modified users to validate page."""
    from app.modules.admin.pages.modif_users import ModifUserDataSource, ModifUsersTable

    ctx = build_table_context(ModifUserDataSource, ModifUsersTable)
    return render_template(
        "admin/pages/generic_table.j2",
        title="Modifications de profils à valider",
        **ctx,
    )


@blueprint.route("/modif_users", methods=["POST"])
@nav(hidden=True)
def modif_users_post():
    """Handle modif users pagination/search."""
    from app.modules.admin.pages.modif_users import ModifUserDataSource

    return handle_table_post(ModifUserDataSource, "admin.modif_users")
