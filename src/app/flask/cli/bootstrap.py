"""Bootstrap CLI commands for application initialization."""
# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

import subprocess
import time
from pathlib import Path

from flask import current_app
from flask.cli import with_appcontext
from flask_security import hash_password
from flask_super.cli import command
from rich import print
from svcs.flask import container

from app.enums import RoleEnum
from app.flask.bootstrap import (
    import_countries,
    import_taxonomies,
    import_zip_codes,
)
from app.flask.extensions import db
from app.models.auth import KYCProfile, Role, User
from app.models.organisation import Organisation
from app.models.repositories import RoleRepository
from app.modules.kyc.ontology_loader import clear_ontology_cache
from app.services.promotions import PromotionService

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
BOX_TITLE1 = "AiPRESS24 vous informe"
BOX_TITLE2 = "AiPRESS24 vous suggère"
BOX_BODY = "..."

DEFAULT_DATA_URL = "https://github.com/aipress24/aipress24-data.git"

BOOTSTRAP_DATA_PATH = Path("bootstrap_data")


@command("bootstrap", short_help="Bootstrap the application database")
@with_appcontext
def bootstrap_cmd() -> None:
    fetch_bootstrap_data()
    bootstrap()


@command("reload-taxonomies", short_help="Re import ontologies and clear caches")
@with_appcontext
def reload_taxonomies_cmd() -> None:
    print("Reloading taxonomies from bootstrap_data...")
    import_taxonomies()
    db.session.commit()
    clear_ontology_cache()
    print("Taxonomies reloaded and cache cleared successfully.")


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
    bootstrap_admin()

    t0 = time.time()
    import_taxonomies()
    db.session.commit()
    print(f"Elapsed time: {time.time() - t0:.2f} seconds")

    import_countries()
    import_zip_codes()
    print(f"Elapsed time: {time.time() - t0:.2f} seconds")


def bootstrap_roles() -> None:
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
    promo_service = container.get(PromotionService)
    promo0 = promo_service.get_promotion(slug=slug0)
    if promo0:
        print("promotions already exist, skipping creation.")
        return

    print("Creating promotions...")
    for slug in BOX_SLUGS:
        if slug.endswith("1"):
            title = BOX_TITLE1
        else:
            title = BOX_TITLE2

        promo_service.store_promotion(slug=slug, title=title, body=BOX_BODY)

    db.session.commit()


def bootstrap_admin() -> None:
    """The first admin of an empty instance, from `BOOTSTRAP_ADMIN_EMAIL` and
    `BOOTSTRAP_ADMIN_PASSWORD` (`FLASK_BOOTSTRAP_ADMIN_*` in the environment).

    Nothing without an email. Once the user exists it is left alone: its
    password is changed in the app, not here.
    """
    email = current_app.config.get("BOOTSTRAP_ADMIN_EMAIL")
    if not email:
        return
    if db.session.query(User).filter_by(email=email).first():
        print(f"Admin {email} already exists, skipping creation.")
        return
    # Dynaconf parses environment values: "123456" would arrive as an int.
    password = current_app.config["BOOTSTRAP_ADMIN_PASSWORD"]
    if not isinstance(password, str):
        msg = "BOOTSTRAP_ADMIN_PASSWORD must be a string: prefix it with '@str '"
        raise TypeError(msg)

    print(f"Creating admin {email}...")
    repo = container.get(RoleRepository)
    org = Organisation(name="AIPress24")
    org.active = True
    # PRESS_MEDIA as well: templates pick the user's community from it.
    user = User(email=email, first_name="Admin", last_name="AIPress24", active=True)
    user.photo = b""
    user.password = hash_password(password)
    user.organisation = org
    user.roles += [
        repo.get_by_name(RoleEnum.ADMIN.name),
        repo.get_by_name(RoleEnum.PRESS_MEDIA.name),
    ]
    db.session.add(
        KYCProfile(
            user=user, profile_id="P001", profile_label="Administrator", match_making={}
        )
    )
    db.session.commit()
