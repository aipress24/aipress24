# Copyright (c) 2021-2024 - Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

import click
from cleez.colors import dim, green, red
from flask import current_app
from flask.cli import with_appcontext
from flask_security import hash_password
from flask_super.cli import command
from flask_super.registry import lookup
from svcs.flask import container

from app.faker import FakerScript, FakerService
from app.flask.extensions import db
from app.flask.sqla import get_multi
from app.models.auth import CommunityEnum, RoleEnum, User

from ...models.repositories import RoleRepository, UserRepository
from . import util
from .bootstrap import PASSWORD, bootstrap_boxes, bootstrap_roles
from .ontologies import _import_ontologies


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
    bootstrap()

    print(green("Generating fake data..."))
    faker = FakerService(db)
    faker.generate_fake_entities()

    print(green("Fixing roles on users..."))
    fix_roles()
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


def bootstrap():
    bootstrap_roles()
    bootstrap_boxes()
    _import_ontologies()


COMMUNITY_TO_ROLE = {
    CommunityEnum.PRESS_MEDIA: RoleEnum.PRESS_MEDIA,
    CommunityEnum.COMMUNICANTS: RoleEnum.PRESS_RELATIONS,
    CommunityEnum.LEADERS_EXPERTS: RoleEnum.EXPERT,
    CommunityEnum.TRANSFORMERS: RoleEnum.TRANSFORMER,
    CommunityEnum.ACADEMICS: RoleEnum.ACADEMIC,
}


def fix_roles():
    role_repo = container.get(RoleRepository)
    roles_map = {role.name: role for role in role_repo.list()}

    user_repo = container.get(UserRepository)
    for i, user in enumerate(user_repo.list()):
        user.email = f"u{i}@aipress24.com"
        user.password = hash_password(PASSWORD)

        role = roles_map[COMMUNITY_TO_ROLE[user.community_primary].name]
        user.roles.append(role)

        if user.community_secondary:
            role = roles_map[COMMUNITY_TO_ROLE[user.community_secondary].name]
            user.roles.append(role)

    db.session.commit()
    db.session.expunge_all()

    for user in user_repo.list():
        assert user.email.endswith("aipress24.com")
        assert len(user.roles) > 0


def check_roles():
    role_repo = container.get(RoleRepository)
    roles_map = {role.name: role for role in role_repo.list()}

    user_repo = container.get(UserRepository)
    for user in user_repo.list():
        roles = []
        role = roles_map[COMMUNITY_TO_ROLE[user.community_primary].name]
        roles.append(role)

        if user.community_secondary:
            role = roles_map[COMMUNITY_TO_ROLE[user.community_secondary].name]
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
