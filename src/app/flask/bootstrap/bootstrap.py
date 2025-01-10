# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from rich import print
from sqlalchemy import func, select

from app.enums import RoleEnum
from app.flask.extensions import db
from app.models.admin import Promotion
from app.models.auth import Role
from app.models.repositories import UserRepository

from ...services.countries import get_countries
from ...services.taxonomies._models import TaxonomyEntry
from .geoloc import import_countries, import_zip_codes
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


def bootstrap_db(app):
    """Bootstrap database content."""

    if app.testing:
        print("Skipping database bootstrap in testing mode")

    with app.app_context():
        print("Creating database tables...")
        db.create_all()

    print("Bootstrapping database content (if needed)...")
    with app.app_context():
        bootstrap_admin(app)
        bootstrap_roles()
        bootstrap_boxes()
        db.session.commit()

    with app.app_context():
        query = select(func.count(TaxonomyEntry.id))
        result = db.session.execute(query).scalar()
        if not result:
            print("No taxonomy entries found, importing ontologies...")
            import_ontologies_content()
            db.session.commit()

    with app.app_context():
        if not get_countries():
            print("Importing geoloc (postal) data...")
            import_countries()
            import_zip_codes()
            db.session.commit()


def bootstrap_admin(app):
    """Create admin user if needed."""
    admin_email = app.config.get("ADMIN_EMAIL")
    if not admin_email:
        return

    admin_password = app.config.get("ADMIN_PASSWORD")
    if not admin_password:
        return

    with app.app_context():
        repo = UserRepository()
        admin = repo.get(email=admin_email)
        if admin:
            print(f"Admin user {admin_email} already exists")
            return


def bootstrap_roles():
    roles = db.session.query(Role).all()
    if roles:
        print("Roles already exist")
        return

    print("Creating roles...")
    # roles = []
    for role_enum in RoleEnum:
        role = Role(name=role_enum.name, description=role_enum.value)
        db.session.add(role)
        # roles.append(role)

    db.session.commit()


def bootstrap_boxes() -> None:
    boxes = db.session.query(Promotion).all()
    if boxes:
        print("Marketing boxes already exist")
        return

    print("Creating marketing boxes...")
    for slug in BOX_SLUGS:
        if slug.endswith("1"):
            title = BOX_TITLE1
        else:
            title = BOX_TITLE2

        promo = Promotion(slug=slug, title=title, body=BOX_BODY)
        db.session.add(promo)

    db.session.commit()
