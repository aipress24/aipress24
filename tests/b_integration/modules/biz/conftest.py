# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Shared fixtures for Biz (Marketplace) integration tests."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

import pytest

from app.models.auth import User
from app.models.organisation import Organisation

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


def _unique_email() -> str:
    return f"biz_{uuid.uuid4().hex[:8]}@example.com"


@pytest.fixture
def test_org(db_session: Session) -> Organisation:
    org = Organisation(name="Biz Test Org")
    db_session.add(org)
    db_session.flush()
    return org


@pytest.fixture
def test_emitter(db_session: Session, test_org: Organisation) -> User:
    user = User(
        email=_unique_email(),
        first_name="Emit",
        last_name="Ter",
        active=True,
    )
    user.organisation = test_org
    user.organisation_id = test_org.id
    db_session.add(user)
    db_session.flush()
    return user


@pytest.fixture
def test_applicant(db_session: Session) -> User:
    user = User(
        email=_unique_email(),
        first_name="Ap",
        last_name="Plicant",
        active=True,
    )
    db_session.add(user)
    db_session.flush()
    return user
