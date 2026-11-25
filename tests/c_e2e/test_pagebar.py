# Copyright (c) 2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""The debug bar shows everything about a request, to administrators only."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
import sqlalchemy as sa
from flask import g

from app.enums import RoleEnum
from app.models.auth import KYCProfile, Role, User
from app.modules.admin.cms import CorporatePage
from tests.c_e2e.conftest import make_authenticated_client

if TYPE_CHECKING:
    from flask import Flask
    from flask.testing import FlaskClient
    from sqlalchemy.orm import Session

PRIVATE_PAGE = "/wire/tab/wall"
PUBLIC_PAGE = "/page/pagebar-test"

BAR = 'class="pagebar-root"'
SQL = 'class="pagebar-sql-text"'


@pytest.fixture
def public_page(db_session: Session) -> None:
    db_session.add(CorporatePage(slug="pagebar-test", title="T", body_md="B"))
    db_session.commit()


def _client(app: Flask, db_session: Session, *roles: RoleEnum) -> FlaskClient:
    user = User(email=f"pagebar-{len(roles)}@example.com", active=True)
    user.profile = KYCProfile()
    for each in roles:
        role = db_session.scalar(sa.select(Role).where(Role.name == each.name))
        user.roles.append(role or Role(name=each.name, description=each.value))
    db_session.add(user)
    db_session.commit()
    return make_authenticated_client(app, user)


def _page(client: FlaskClient, url: str) -> str:
    response = client.get(url)
    assert response.status_code == 200
    return response.text


@pytest.mark.parametrize("url", [PRIVATE_PAGE, PUBLIC_PAGE])
def test_an_administrator_sees_the_bar_and_the_sql(
    app: Flask, db_session: Session, public_page: None, url: str
) -> None:
    client = _client(app, db_session, RoleEnum.PRESS_MEDIA, RoleEnum.ADMIN)
    assert not app.debug
    page = _page(client, url)
    assert BAR in page
    assert SQL in page


@pytest.mark.parametrize("url", [PRIVATE_PAGE, PUBLIC_PAGE])
def test_a_member_does_not(
    app: Flask, db_session: Session, public_page: None, url: str
) -> None:
    client = _client(app, db_session, RoleEnum.PRESS_MEDIA)
    page = _page(client, url)
    assert BAR not in page
    assert SQL not in page


def test_a_visitor_does_not(client: FlaskClient, public_page: None) -> None:
    assert BAR not in _page(client, PUBLIC_PAGE)


def test_a_visitor_gets_none_after_an_administrator(
    app: Flask, db_session: Session, client: FlaskClient, public_page: None
) -> None:
    """The bar keeps its data per thread, which serves them both."""
    admin = _client(app, db_session, RoleEnum.PRESS_MEDIA, RoleEnum.ADMIN)
    assert BAR in _page(admin, PUBLIC_PAGE)
    # The fixtures hold an app context, where flask-login remembers the user.
    g.pop("_login_user")
    assert BAR not in _page(client, PUBLIC_PAGE)
