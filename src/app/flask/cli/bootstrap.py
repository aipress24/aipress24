# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

import decimal
import subprocess
import time
import traceback
from pathlib import Path

import yaml
from flask import current_app
from flask.cli import with_appcontext
from flask_security import hash_password
from flask_super.cli import command
from rich import print
from sqlalchemy_utils.types.arrow import arrow
from svcs.flask import container

from app.enums import RoleEnum
from app.flask.bootstrap import import_countries, import_taxonomies, import_zip_codes
from app.flask.extensions import db
from app.models.admin import Promotion
from app.models.auth import KYCProfile, Role, User
from app.models.repositories import RoleRepository, UserRepository
from app.services.promotions import get_promotion

BOX_SLUGS = [
    "wire/1",
    "wire/2",
    "events/1",
    "events/2",
    "biz/1",
    "biz/2",
    "swork/1",
    "swork/2",
]
BOX_TITLE1 = "AIpress24 vous informe"
BOX_TITLE2 = "AIpress24 vous suggère"
BOX_BODY = "..."

DEFAULT_DATA_URL = "https://github.com/aipress24/aipress24-data.git"

BOOTSTRAP_DATA_PATH = Path("bootstrap_data")


def decimal_constructor(loader, node):
    value = loader.construct_scalar(node)
    return decimal.Decimal(value)


def arrow_constructor(loader, node):
    value = loader.construct_scalar(node)
    return arrow.get(value)


yaml.SafeLoader.add_constructor("!decimal", decimal_constructor)
yaml.SafeLoader.add_constructor("!arrow", arrow_constructor)


#
# Other operational commands
#
@command("bootstrap-users", short_help="Bootstrap users")
@with_appcontext
def bootstrap_users_cmd() -> None:
    for path in Path("users").glob("*.yaml"):
        try:
            user = bootstrap_user(path)
            print(f"Imported user {user.email} from file: {path}")
        except Exception as e:
            print(f"Error: {e}")
            traceback.print_exc()
            print("Could not import user from file: ", path)


def bootstrap_user(path):
    user_repo = UserRepository(session=db.session)
    role_repo = RoleRepository(session=db.session)

    data = yaml.load(path.open(), Loader=yaml.SafeLoader)

    user_id = data["id"]
    if user_repo.count(id=user_id):
        user_repo.delete(user_id)

    password = data.pop("_password")
    role_name = data.pop("_role")
    profile_data = data.pop("_profile")
    is_admin = data.pop("_is_admin", False)

    user = User(**data)
    user.password = hash_password(password)

    role = role_repo.get_by_name(role_name)
    user.roles.append(role)
    if is_admin:
        admin_role = role_repo.get_by_name("ADMIN")
        user.roles.append(admin_role)

    profile = KYCProfile(**profile_data)
    user.profile = profile

    user_repo.add(user)
    db.session.commit()
    return user


@command("bootstrap", short_help="Bootstrap the application database")
@with_appcontext
def bootstrap_cmd() -> None:
    fetch_bootstrap_data()
    bootstrap()


@command("fetch-bootstrap-data", short_help="Fetch the bootstrap data")
@with_appcontext
def fetch_bootstrap_data_cmd() -> None:
    fetch_bootstrap_data()


def fetch_bootstrap_data() -> None:
    if not BOOTSTRAP_DATA_PATH.exists():
        print("Downloading data...")
        git_url = current_app.config.get("BOOTSTRAP_DATA_URL", DEFAULT_DATA_URL)
        subprocess.run(
            ["/usr/bin/git", "clone", git_url, str(BOOTSTRAP_DATA_PATH)], check=False
        )


def bootstrap() -> None:
    bootstrap_roles()
    bootstrap_promotions()

    t0 = time.time()
    import_taxonomies()
    db.session.commit()
    print(f"Ellapsed time: {time.time() - t0:.2f} seconds")

    import_countries()
    import_zip_codes()
    print(f"Ellapsed time: {time.time() - t0:.2f} seconds")


def bootstrap_roles():
    repo = container.get(RoleRepository)
    roles = repo.list()
    if roles:
        print("Roles already exist, skipping creation.")
        return

    print("Creating roles...")
    for role_enum in RoleEnum:
        role = Role(name=role_enum.name, description=role_enum.value)
        repo.add(role, auto_commit=True)


def bootstrap_promotions() -> None:
    slug0 = BOX_SLUGS[0]
    promo0 = get_promotion(slug0)
    if promo0:
        print("promotions already exist, skipping creation.")
        return

    print("Creating promotions...")
    for slug in BOX_SLUGS:
        if slug.endswith("1"):
            title = BOX_TITLE1
        else:
            title = BOX_TITLE2

        promo = Promotion(slug=slug, title=title, body=BOX_BODY)
        db.session.add(promo)

    db.session.commit()
