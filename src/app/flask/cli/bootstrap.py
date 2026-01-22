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
from flask_super.cli import command
from rich import print
from svcs.flask import container

from app.enums import RoleEnum
from app.flask.bootstrap import import_countries, import_taxonomies, import_zip_codes
from app.flask.extensions import db
from app.models.auth import Role
from app.models.repositories import RoleRepository
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
    for role_enum in RoleEnum:  # type: ignore
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
