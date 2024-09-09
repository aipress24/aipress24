# Copyright (c) 2021-2024 - Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

import click
from cleez.colors import dim, green, red
from flask import current_app
from flask.cli import with_appcontext
from flask_super.cli import command
from flask_super.registry import lookup
from svcs.flask import container

from app.faker import FakerScript, FakerService
from app.flask.extensions import db
from app.flask.sqla import get_multi
from app.models.auth import User
from app.modules.kyc.community_role import (
    append_user_role_from_community,
    community_to_role_enum,
    generate_roles_map,
)

from ...models.repositories import UserRepository
from . import util
from .bootstrap import bootstrap_function


#
# Faker
#
@command(short_help="Generate fake data")
@click.option("--clean/--no-clean", default=False)
@with_appcontext
def fake(clean) -> None:
    print(green("Setting up database"))
    db_setup(clean)

    print(green("Bootstrapping master data..."))
    bootstrap_function()

    print(green("Generating fake data..."))
    faker = FakerService(db)
    faker.generate_fake_entities()

    print(green("Fixing roles on users..."))
    fix_roles()
    create_admins()
    check_roles()

    print(green("Running additional faking scripts..."))
    run_fake_scripts()

    db.session.commit()


def db_setup(clean: bool) -> None:
    if clean:
        util.drop_tables()

    print("Creating tables...")
    db.create_all()
    print("... done")

    if current_app.debug:
        util.inspect()

    users = get_multi(User)
    if len(users) > 0:
        print(red("Database is not empty:"))
        return


def fix_roles():
    user_repo = container.get(UserRepository)
    role_map = generate_roles_map()
    for user in user_repo.list():
        append_user_role_from_community(role_map, user)
        # user.roles.append(role_map["ADMIN"])

    db.session.commit()
    db.session.expunge_all()

    for user in user_repo.list():
        assert user.email.endswith("aipress24.com")
        assert len(user.roles) > 0


def create_admins():
    user_repo = container.get(UserRepository)
    role_map = generate_roles_map()
    role_admin = role_map["ADMIN"]
    for idx in (1, 2, 3, 4, 5):
        user = user_repo.get_one(email=f"u{idx}@aipress24.com")
        user.add_role(role_admin)
        print(user, "granted role ADMIN")

    db.session.commit()
    db.session.expunge_all()


def check_roles():
    user_repo = container.get(UserRepository)
    role_map = generate_roles_map()

    for user in user_repo.list():
        # fixme: this checks only one role
        roles = []
        role = community_to_role_enum(role_map, user.community)
        roles.append(role)

        for role in roles:
            assert user.has_role(role.name)
            assert user.has_role(role)


def run_fake_scripts():
    scripts = [cls() for cls in lookup(FakerScript)]
    for script in scripts:
        print(dim(f"Running faker script: {script.name}"))
        script.run()


def help(scripts):
    print("Usage: 'flask fake <script_name> <args> where <script_name> can be:\n")
    for script in scripts:
        print(f"- {script.name}: {script.description}")
