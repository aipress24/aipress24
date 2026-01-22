"""CLI commands for role/user management (extends Flask-Security groups)."""
# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

import click
from flask import current_app
from flask.cli import with_appcontext
from flask_security import SQLAlchemyUserDatastore
from rich.console import Console
from rich.table import Table


def register_roles_commands(app):
    """Register additional commands to the Flask-Security roles group."""
    security = app.extensions.get("security")
    if security is None:
        return

    roles_group = app.cli.commands.get("roles")
    if roles_group is None:
        return

    @roles_group.command("list")
    @with_appcontext
    def list_roles():
        """List all available roles."""
        datastore: SQLAlchemyUserDatastore = current_app.extensions[
            "security"
        ].datastore
        roles = datastore.role_model.query.order_by("name").all()

        console = Console()
        table = Table(title="Available Roles")
        table.add_column("Name", style="cyan")
        table.add_column("Description", style="green")

        for role in roles:
            table.add_row(role.name, role.description or "")

        console.print(table)
        console.print(f"\nTotal: {len(roles)} roles")


def register_users_commands(app):
    """Register additional commands to the Flask-Security users group."""
    security = app.extensions.get("security")
    if security is None:
        return

    users_group = app.cli.commands.get("users")
    if users_group is None:
        return

    @users_group.command("list")
    @click.option("--limit", "-n", default=50, help="Maximum number of users to show")
    @click.option("--active/--all", default=True, help="Show only active users")
    @with_appcontext
    def list_users(limit, active):
        """List users."""
        datastore: SQLAlchemyUserDatastore = current_app.extensions[
            "security"
        ].datastore
        query = datastore.user_model.query.order_by("email")
        if active:
            query = query.filter_by(active=True)
        users = query.limit(limit).all()
        total = query.count()

        console = Console()
        table = Table(title=f"Users ({'active only' if active else 'all'})")
        table.add_column("Email", style="cyan")
        table.add_column("Name", style="green")
        table.add_column("Active", style="yellow")
        table.add_column("Roles", style="magenta")

        for user in users:
            name = f"{user.first_name or ''} {user.last_name or ''}".strip() or "-"
            active_str = "Yes" if user.active else "No"
            roles_str = ", ".join(r.name for r in user.roles) or "-"
            table.add_row(user.email, name, active_str, roles_str)

        console.print(table)
        if total > limit:
            console.print(f"\nShowing {limit} of {total} users (use --limit to show more)")
        else:
            console.print(f"\nTotal: {total} users")
