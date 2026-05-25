# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Override WIP fixtures for eventroom tests.

Eventroom requires PRESS_RELATIONS (or EXPERT/TRANSFORMER/ACADEMIC) instead of
PRESS_MEDIA. This conftest overrides test_user so all eventroom tests get a user
with the correct role.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from app.enums import RoleEnum
from app.models.auth import KYCProfile, Role, User
from app.models.organisation import Organisation

from tests.c_e2e.conftest import make_authenticated_client

if TYPE_CHECKING:
    from flask import Flask
    from flask.testing import FlaskClient


@pytest.fixture
def test_user(fresh_db, test_org: Organisation) -> User:
    """Create a test user with PRESS_RELATIONS role."""
    db_session = fresh_db.session

    role = Role(
        name=RoleEnum.PRESS_RELATIONS.name,
        description=RoleEnum.PRESS_RELATIONS.value,
    )
    db_session.add(role)
    db_session.commit()

    profile = KYCProfile()
    user = User(
        email="wip-eventroom@example.com",
        first_name="John",
        last_name="Doe",
    )
    user.profile = profile
    user.photo = b""
    user.active = True
    user.organisation = test_org
    user.organisation_id = test_org.id
    user.roles.append(role)
    db_session.add(user)
    db_session.commit()

    return user


@pytest.fixture
def logged_in_client(app: Flask, test_user: User) -> FlaskClient:
    """Provide a logged-in Flask test client."""
    return make_authenticated_client(app, test_user)
