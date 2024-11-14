# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from flask.cli import with_appcontext
from flask_super.cli import command
from rich import print
from sqlalchemy.orm import scoped_session
from svcs.flask import container

from app.enums import RoleEnum
from app.flask.extensions import db
from app.models.admin import Promotion
from app.models.auth import Role

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
    bootstrap_boxes()
    import_ontologies_content()


def bootstrap_roles():
    db_session = container.get(scoped_session)

    print("Creating roles...")
    # roles = []
    for role_enum in RoleEnum:
        role = Role(name=role_enum.name, description=role_enum.value)
        db_session.add(role)
        # roles.append(role)

    db_session.commit()


def bootstrap_boxes() -> None:
    print("Creating marketing boxes..")
    for slug in BOX_SLUGS:
        if slug.endswith("1"):
            title = BOX_TITLE1
        else:
            title = BOX_TITLE2

        promo = Promotion(slug=slug, title=title, body=BOX_BODY)
        db.session.add(promo)

    db.session.commit()
