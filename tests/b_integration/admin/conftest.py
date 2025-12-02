# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Shared fixtures for admin module tests."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from app.enums import RoleEnum
from app.models.auth import Role, User

if TYPE_CHECKING:
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
