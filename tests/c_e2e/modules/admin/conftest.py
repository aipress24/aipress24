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
from app.models.auth import KYCProfile, Role, User
from app.models.organisation import Organisation
from tests.c_e2e.conftest import make_authenticated_client

if TYPE_CHECKING:
    from flask import Flask
    from flask.testing import FlaskClient
    from sqlalchemy.orm import Session


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
    db_session.commit()
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
    db_session.commit()
    return users


@pytest.fixture
def admin_user(db_session: Session) -> User:
    """Create admin user for tests.

    Uses commit() instead of flush() so Flask-Security can find the user
    when authenticating requests.

    The admin user includes:
    - ADMIN role (for admin access)
    - PRESS_MEDIA role (for community detection in templates)
    - An Organisation (required for user setup)
    - A KYCProfile (required for profile pages)
    """
    existing_user = db_session.query(User).filter_by(email="admin@example.com").first()
    if existing_user:
        return existing_user

    # Create admin role
    admin_role = db_session.query(Role).filter_by(name=RoleEnum.ADMIN.name).first()
    if not admin_role:
        admin_role = Role(name=RoleEnum.ADMIN.name, description="Administrator")
        db_session.add(admin_role)

    # Create press_media role (required for community detection)
    press_role = (
        db_session.query(Role).filter_by(name=RoleEnum.PRESS_MEDIA.name).first()
    )
    if not press_role:
        press_role = Role(name=RoleEnum.PRESS_MEDIA.name, description="Press & Media")
        db_session.add(press_role)

    db_session.commit()

    # Create organisation for admin user
    org = Organisation(name="Admin Test Org")
    org.active = True
    db_session.add(org)
    db_session.commit()

    # Create admin user with both roles
    user = User(
        email="admin@example.com",
        first_name="Admin",
        last_name="User",
        active=True,
    )
    user.photo = b""
    user.roles.append(admin_role)
    user.roles.append(press_role)
    user.organisation = org
    user.organisation_id = org.id
    db_session.add(user)
    db_session.commit()

    # Create KYCProfile for admin user (profile_id P001 = Journaliste)
    profile = KYCProfile(
        user=user,
        profile_id="P001",
        profile_label="Administrator",
        match_making={},
    )
    db_session.add(profile)
    db_session.commit()

    return user


@pytest.fixture
def non_admin_user(db_session: Session) -> User:
    """Create non-admin user for tests."""
    user = User(email="regular@example.com")
    user.photo = b""
    user.active = True
    db_session.add(user)
    db_session.commit()
    return user


@pytest.fixture
def admin_client(app: Flask, admin_user: User) -> FlaskClient:
    """Provide a Flask test client logged in as admin."""
    return make_authenticated_client(app, admin_user)
