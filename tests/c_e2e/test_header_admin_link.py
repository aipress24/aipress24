# Copyright (c) 2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""The header links to the administration for administrators only."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
import sqlalchemy as sa
from bs4 import BeautifulSoup

from app.enums import RoleEnum
from app.models.auth import KYCProfile, Role, User
from tests.c_e2e.conftest import make_authenticated_client

if TYPE_CHECKING:
    from flask import Flask
    from sqlalchemy.orm import Session

ADMIN_LINK = 'a[href="/admin/"][data-tip="Admin"]'


@pytest.mark.parametrize(
    ("roles", "expected"),
    [([RoleEnum.PRESS_MEDIA, RoleEnum.ADMIN], 1), ([RoleEnum.PRESS_MEDIA], 0)],
)
def test_the_admin_link(
    app: Flask, db_session: Session, roles: list[RoleEnum], expected: int
) -> None:
    user = User(email=f"header-{len(roles)}@example.com", active=True)
    user.profile = KYCProfile()
    for each in roles:
        role = db_session.scalar(sa.select(Role).where(Role.name == each.name))
        user.roles.append(role or Role(name=each.name, description=each.value))
    db_session.add(user)
    db_session.commit()

    response = make_authenticated_client(app, user).get("/wire/tab/wall")

    assert response.status_code == 200
    page = BeautifulSoup(response.text, "html.parser")
    assert len(page.select(ADMIN_LINK)) == expected
