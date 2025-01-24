# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from flask.cli import with_appcontext
from flask_super.cli import command
from rich import print
from sqlalchemy import select
from svcs.flask import container

from app.enums import RoleEnum
from app.flask.extensions import db
from app.models.admin import Promotion
from app.models.auth import Role
from app.models.repositories import RoleRepository
from app.services.promotions import get_promotion
from app.services.taxonomies import TaxonomyEntry

from .ontologies import import_ontologies_content

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


#
# Other operational commands
#
@command()
@with_appcontext
def bootstrap() -> None:
    bootstrap_function()


def bootstrap_function() -> None:
    bootstrap_roles()
    bootstrap_promotions()
    bootstrap_ontologies()


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
    print("Creating promotions..")
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


def bootstrap_ontologies():
    query = select(TaxonomyEntry)
    result = db.session.execute(query).scalar()
    if result:
        print("Ontologies already exist, skipping creation.")
        return

    print("Creating ontologies...")
    import_ontologies_content()
