# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Fixtures for admin module E2E tests.

Uses fresh_db (drop/create) to ensure database tables exist.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from app.enums import OrganisationTypeEnum, RoleEnum
from app.models.auth import Role, User
from app.models.organisation import Organisation
from tests.c_e2e.conftest import make_authenticated_client

if TYPE_CHECKING:
    from flask import Flask
    from flask.testing import FlaskClient
    from sqlalchemy.orm import Session


@pytest.fixture(autouse=True)
def db_session(fresh_db) -> Session:
    """Override modules/conftest.py db_session to use fresh_db."""
    return fresh_db.session


@pytest.fixture
def sample_organisations(db_session: Session) -> list[Organisation]:
    """Create sample organisations for export tests."""
    orgs = [
        Organisation(name="Org A", type=OrganisationTypeEnum.MEDIA),
        Organisation(name="Org B", type=OrganisationTypeEnum.COM),
        Organisation(name="Org C", type=OrganisationTypeEnum.OTHER),
    ]
    for org in orgs:
        db_session.add(org)
    db_session.flush()
    return orgs


@pytest.fixture
def sample_users(
    db_session: Session, sample_organisations: list[Organisation]
) -> list[User]:
    """Create sample users for export tests."""
    users = []
    for i, org in enumerate(sample_organisations):
        user = User(email=f"user{i}@example.com")
        user.photo = b""
        user.active = True
        user.organisation = org
        db_session.add(user)
        users.append(user)
    db_session.flush()
    return users


@pytest.fixture
def admin_user(db_session: Session) -> User:
    """Create admin user for tests."""
    existing_user = db_session.query(User).filter_by(email="admin@example.com").first()
    if existing_user:
        return existing_user

    admin_role = db_session.query(Role).filter_by(name=RoleEnum.ADMIN.name).first()
    if not admin_role:
        admin_role = Role(name=RoleEnum.ADMIN.name, description="Administrator")
        db_session.add(admin_role)
        db_session.flush()

    user = User(email="admin@example.com")
    user.photo = b""
    user.roles.append(admin_role)
    db_session.add(user)
    db_session.flush()
    return user


@pytest.fixture
def non_admin_user(db_session: Session) -> User:
    """Create non-admin user for tests."""
    user = User(email="regular@example.com")
    user.photo = b""
    db_session.add(user)
    db_session.flush()
    return user


@pytest.fixture
def admin_client(app: Flask, admin_user: User) -> FlaskClient:
    """Provide a Flask test client logged in as admin."""
    return make_authenticated_client(app, admin_user)
