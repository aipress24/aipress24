# Copyright (c) 2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only
"""The pages where members and administrators manage API keys."""

from __future__ import annotations

import json
import re
from datetime import timedelta
from types import SimpleNamespace

import pytest
import sqlalchemy as sa
from flask import Flask, g, get_flashed_messages
from flask.testing import FlaskClient
from flask_security.signals import password_changed, password_reset
from sqlalchemy.orm import Session

from app.enums import RoleEnum
from app.models.auth import KYCProfile, User
from app.modules.api_v1.models import ApiToken, _utcnow
from app.modules.api_v1.tokens import MAX_ACTIVE_TOKENS, active_tokens, issue_token
from app.services.emails import ApiKeyCreatedMail
from tests.c_e2e.conftest import make_authenticated_client

from .conftest import _role

URL = "/preferences/api-keys"
FORM = {"name": "Laptop", "scopes": ["read:self", "write:content"], "days": "90"}


@pytest.fixture
def members(db_session: Session) -> SimpleNamespace:
    owner = User(email="owner@example.com", active=True)
    other = User(email="other@example.com", active=True)
    admin = User(email="admin@example.com", active=True)
    admin.roles.append(_role(db_session, RoleEnum.ADMIN))
    for user in (owner, other, admin):
        user.photo = b""
        user.profile = KYCProfile(
            contact_type="PRESSE", profile_id="P001", profile_community="PRESS_MEDIA"
        )
    db_session.add_all([owner, other, admin])
    db_session.commit()
    return SimpleNamespace(owner=owner, other=other, admin=admin)


@pytest.fixture
def owner_client(app: Flask, members: SimpleNamespace) -> FlaskClient:
    return _log_in(app, members.owner)


@pytest.fixture
def key(db_session: Session, members: SimpleNamespace) -> ApiToken:
    token, _secret = issue_token(
        db_session, members.owner, "Existing", ["read:self"], None
    )
    db_session.commit()
    return token


def _log_in(app: Flask, user: User) -> FlaskClient:
    """A logged-in client that loads its user from the session.

    The test's application context outlives requests, so logging in leaves the
    user on ``g``, where Flask-Security does not see a session login.
    """
    client = make_authenticated_client(app, user)
    g.pop("_login_user", None)
    return client


def _count(db_session: Session) -> int:
    return db_session.scalar(sa.select(sa.func.count(ApiToken.id))) or 0


def test_a_created_key_is_shown_once_and_works(
    owner_client: FlaskClient, client: FlaskClient, db_session: Session
) -> None:
    response = owner_client.post(URL, data=FORM)

    assert response.status_code == 200
    assert "no-store" in response.headers["Cache-Control"]
    match = re.search(r"a24_[\w-]{30,}", response.text)
    assert match
    api = client.get("/api/v1/me", headers={"Authorization": f"Bearer {match[0]}"})
    assert json.loads(api.data)["email"] == "owner@example.com"

    page = owner_client.get(URL).text
    assert match[0] not in page
    assert "Laptop" in page


def test_a_created_key_expires(owner_client: FlaskClient, db_session: Session) -> None:
    owner_client.post(URL, data=FORM)

    token = db_session.scalars(sa.select(ApiToken)).one()
    assert token.is_usable(_utcnow() + timedelta(days=89))
    assert not token.is_usable(_utcnow() + timedelta(days=91))


@pytest.mark.parametrize(
    "change",
    [
        {"name": " "},
        {"name": "x" * 121},
        {"scopes": []},
        {"scopes": ["read:directory"]},
        {"scopes": ["read:self", "made:up"]},
        {"days": "9999"},
        {"days": ""},
    ],
)
def test_invalid_requests_create_nothing(
    owner_client: FlaskClient, db_session: Session, change: dict
) -> None:
    response = owner_client.post(URL, data={**FORM, **change})

    assert response.status_code == 422
    assert 'role="alert"' in response.text
    assert _count(db_session) == 0


def test_the_number_of_active_keys_is_limited(
    owner_client: FlaskClient, db_session: Session
) -> None:
    for _ in range(MAX_ACTIVE_TOKENS):
        assert owner_client.post(URL, data=FORM).status_code == 200
    assert owner_client.post(URL, data=FORM).status_code == 422

    token = db_session.scalars(sa.select(ApiToken).limit(1)).one()
    owner_client.post(f"{URL}/{token.id}/revoke")
    assert owner_client.post(URL, data=FORM).status_code == 200


def test_an_old_login_must_be_confirmed(
    owner_client: FlaskClient, db_session: Session
) -> None:
    with owner_client.session_transaction() as session:
        session["fs_paa"] = session["fs_paa"] - 2 * 24 * 3600
        session.pop("fs_gexp", None)

    for response in (owner_client.get(URL), owner_client.post(URL, data=FORM)):
        assert response.status_code == 302
        assert "/verify?next=" in response.headers["Location"]
    assert _count(db_session) == 0
    assert 'type="password"' in owner_client.get(response.headers["Location"]).text


def test_a_member_revokes_their_own_key(
    owner_client: FlaskClient, db_session: Session, key: ApiToken
) -> None:
    response = owner_client.post(f"{URL}/{key.id}/revoke")

    assert response.status_code == 302
    db_session.refresh(key)
    assert key.is_revoked()
    assert "Existing" not in owner_client.get(URL).text


def test_a_member_revokes_all_their_keys_and_only_theirs(
    owner_client: FlaskClient,
    members: SimpleNamespace,
    db_session: Session,
    key: ApiToken,
) -> None:
    issue_token(db_session, members.owner, "Second", ["read:self"], None)
    foreign, _ = issue_token(db_session, members.other, "Foreign", ["read:self"], None)
    db_session.commit()

    owner_client.post(f"{URL}/revoke-all")

    db_session.expire_all()
    assert active_tokens(db_session, members.owner) == []
    assert not foreign.is_revoked()


def test_the_owner_is_told_of_a_new_key(
    app: Flask, owner_client: FlaskClient, db_session: Session
) -> None:
    outbox = app.extensions["mailman"].outbox = []
    response = owner_client.post(URL, data={**FORM, "name": "<b>Laptop</b>"})

    [mail] = outbox
    assert mail.to == ["owner@example.com"]
    assert "&lt;b&gt;Laptop" in mail.body
    assert "Créer, modifier, publier" in mail.body
    assert re.search(rf'href="https?://[^/"]+{URL}"', mail.body)
    secret = re.search(r"a24_[\w-]{30,}", response.text)
    assert secret
    assert secret[0] not in mail.body


def test_a_key_is_shown_even_if_its_alert_cannot_be_sent(
    owner_client: FlaskClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    def refuse(_mail: ApiKeyCreatedMail) -> bool:
        raise ConnectionRefusedError

    monkeypatch.setattr(ApiKeyCreatedMail, "send", refuse)
    response = owner_client.post(URL, data=FORM)

    assert response.status_code == 200
    assert re.search(r"a24_[\w-]{30,}", response.text)


def test_a_new_password_recalls_the_active_keys(
    app: Flask, members: SimpleNamespace, key: ApiToken
) -> None:
    for signal in (password_changed, password_reset):
        with app.test_request_context():
            signal.send(app, user=members.owner)
            assert "(1)" in get_flashed_messages()[0]
        with app.test_request_context():
            signal.send(app, user=members.other)
            assert get_flashed_messages() == []
    assert not key.is_revoked()


def test_a_password_set_from_the_command_line_shows_nothing(
    app: Flask, members: SimpleNamespace, key: ApiToken
) -> None:
    password_changed.send(app, user=members.owner)


def test_a_member_neither_sees_nor_revokes_another_members_key(
    app: Flask, members: SimpleNamespace, db_session: Session, key: ApiToken
) -> None:
    client = _log_in(app, members.other)

    assert "Existing" not in client.get(URL).text
    assert client.post(f"{URL}/{key.id}/revoke").status_code == 404
    db_session.refresh(key)
    assert not key.is_revoked()


def test_an_anonymous_visitor_is_sent_to_login(
    client: FlaskClient, db_session: Session, key: ApiToken
) -> None:
    for response in (
        client.get(URL),
        client.post(URL, data=FORM),
        client.post(f"{URL}/{key.id}/revoke"),
    ):
        assert response.status_code == 302
        assert "/login?next=" in response.headers["Location"]
    db_session.refresh(key)
    assert not key.is_revoked()


def test_an_admin_sees_and_revokes_every_key(
    app: Flask, members: SimpleNamespace, db_session: Session, key: ApiToken
) -> None:
    client = _log_in(app, members.admin)

    page = client.get("/admin/api-keys").text
    assert "Existing" in page
    assert "owner@example.com" in page
    assert key.token_hash not in page

    client.post(f"/admin/api-keys/{key.id}/revoke")
    db_session.refresh(key)
    assert key.is_revoked()


def test_only_admins_reach_the_admin_page(
    owner_client: FlaskClient, db_session: Session, key: ApiToken
) -> None:
    assert owner_client.get("/admin/api-keys").status_code != 200
    owner_client.post(f"/admin/api-keys/{key.id}/revoke")
    db_session.refresh(key)
    assert not key.is_revoked()


def test_the_preferences_menu_leads_to_the_keys(owner_client: FlaskClient) -> None:
    assert f'href="{URL}"' in owner_client.get("/preferences/interests").text
