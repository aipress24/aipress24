"""CLI commands for role/user management (extends Flask-Security groups)."""
# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

import click
import sqlalchemy as sa
from flask.cli import with_appcontext
from rich.console import Console
from rich.table import Table

from app.flask.extensions import db
from app.models.auth import Role, User


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
        roles = db.session.scalars(sa.select(Role).order_by(Role.name)).all()

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
        query = sa.select(User)
        if active:
            query = query.where(User.active)
        users = db.session.scalars(query.order_by(User.email).limit(limit)).all()
        total = db.session.scalar(sa.select(sa.func.count()).select_from(query.subquery()))

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
            console.print(
                f"\nShowing {limit} of {total} users (use --limit to show more)"
            )
        else:
            console.print(f"\nTotal: {total} users")
