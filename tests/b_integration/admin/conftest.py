# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Shared fixtures for admin module tests."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from flask import Flask, session
from flask_security import login_user

from app.enums import RoleEnum
from app.models.auth import KYCProfile, Role, User
from app.models.organisation import Organisation

if TYPE_CHECKING:
    from flask.testing import FlaskClient
    from sqlalchemy.orm import Session


@pytest.fixture
def admin_user(db_session: Session) -> User:
    """Create admin user for tests.

    Note: Checks if user exists within the current transaction to allow
    multiple fixtures/tests to reuse the same user. The transaction rollback
    ensures isolation between tests.
    """
    # Check if admin user already exists in current transaction
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
    db_session.flush()  # Use flush() instead of commit() to preserve transaction isolation
    return user


@pytest.fixture
def non_admin_user(db_session: Session) -> User:
    """Create non-admin user for tests.

    Note: Each test runs in its own transaction that gets rolled back,
    so we don't need to check if the user already exists.
    """
    user = User(email="regular@example.com")
    user.photo = b""
    db_session.add(user)
    db_session.flush()  # Use flush() instead of commit() to preserve transaction isolation
    return user


def _get_or_create_role(db_session: Session, name: str, description: str) -> Role:
    """Get existing role or create new one."""
    role = db_session.query(Role).filter_by(name=name).first()
    if not role:
        role = Role(name=name, description=description)
        db_session.add(role)
        db_session.flush()
    return role


@pytest.fixture
def admin_client(app: Flask, db) -> FlaskClient:
    """Create a test client logged in as admin."""
    db_session = db.session

    # Get or create ADMIN role (uppercase, as checked by has_role)
    admin_role = _get_or_create_role(db_session, "ADMIN", "Administrator")

    # Get or create PRESS_MEDIA role (required for community/templates)
    press_role = _get_or_create_role(
        db_session, RoleEnum.PRESS_MEDIA.name, "Press & Media"
    )

    # Check if admin user already exists
    user = db_session.query(User).filter_by(email="admin@example.com").first()
    if not user:
        # Create organisation for admin user
        org = Organisation(name="Admin Org")
        db_session.add(org)
        db_session.flush()

        # Create admin user with both roles
        user = User(
            email="admin@example.com",
            first_name="Admin",
            last_name="User",
            active=True,
        )
        user.roles.append(admin_role)
        user.roles.append(press_role)
        user.organisation = org
        user.organisation_id = org.id
        db_session.add(user)
        db_session.flush()

        # Create KYCProfile for admin user (required for job_title property)
        profile = KYCProfile(user=user, profile_label="Administrator")
        db_session.add(profile)
        db_session.flush()

    # Create test client and authenticate
    client = app.test_client()
    with app.test_request_context():
        login_user(user)
        with client.session_transaction() as sess:
            for key, value in session.items():
                sess[key] = value

    return client
