"""CLI commands for one-off data fixes."""
# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

import click
from flask.cli import with_appcontext
from flask_super.cli import group

from app.flask.extensions import db
from app.models.auth import User
from app.services.roles import generate_roles_map


@group(short_help="One-off data fixes")
def fix() -> None:
    """Commands for one-off data fixes."""


@fix.command("roles", short_help="Fix user roles")
@with_appcontext
def fix_roles_cmd() -> None:
    role_map = generate_roles_map()
    role_admin = role_map["ADMIN"]
    role_press = role_map["PRESS_MEDIA"]
    users = db.session.query(User).order_by(User.id).all()
    for user in users:
        if not user.has_role(role_admin):
            continue
        if user.has_role(role_press):
            continue
        user.remove_role(role_admin)
    for user in users:
        if user.has_role(role_admin):
            print(user.email, user.roles)
    db.session.commit()


@fix.command("test-user", short_help="Fix test user details")
@click.argument("email")
@click.argument("first_name")
@click.argument("last_name")
@with_appcontext
def fix_test_user_cmd(email, first_name, last_name) -> None:
    role_map = generate_roles_map()
    role_admin = role_map["ADMIN"]
    users = db.session.query(User).order_by(User.id).all()
    for user in users:
        if user.has_role(role_admin):
            user.email = email
            user.first_name = first_name
            user.last_name = last_name
            db.session.commit()
            break
