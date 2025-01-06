# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from app.flask.extensions import db
from app.models.repositories import UserRepository


def bootstrap_data(app):
    create_db(app)
    create_admin_if_needed(app)


def create_db(app):
    with app.app_context():
        db.create_all()


def create_admin_if_needed(app):
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
