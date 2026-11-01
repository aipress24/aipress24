# Copyright (c) 2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""`flask bootstrap` creates the first admin from the configuration, once."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from flask_security import verify_password

from app.enums import RoleEnum
from app.flask.cli.bootstrap import bootstrap_admin
from app.flask.extensions import db
from app.models.auth import Role, User

if TYPE_CHECKING:
    from collections.abc import Iterator

    from flask import Config

EMAIL = "first-admin@example.com"


@pytest.fixture
def config(app, monkeypatch) -> Iterator[Config]:
    """The admin settings and the roles it gets. `bootstrap_admin` commits, which
    the `db_session` fixture doesn't roll back: what it made is removed after."""
    roles = [
        Role(name=r.name, description=r.value)
        for r in (RoleEnum.ADMIN, RoleEnum.PRESS_MEDIA)
    ]
    db.session.add_all(roles)
    monkeypatch.setitem(app.config, "BOOTSTRAP_ADMIN_EMAIL", EMAIL)
    monkeypatch.setitem(app.config, "BOOTSTRAP_ADMIN_PASSWORD", "s3cret")
    yield app.config
    for user in admins():
        db.session.delete(user.profile)
        db.session.delete(user.organisation)
        db.session.delete(user)
    for role in roles:
        db.session.delete(role)
    db.session.commit()


def admins() -> list[User]:
    return db.session.query(User).filter_by(email=EMAIL).all()


def test_admin_is_created_once(config):
    bootstrap_admin()
    config["BOOTSTRAP_ADMIN_PASSWORD"] = "changed"
    bootstrap_admin()
    [user] = admins()
    assert verify_password("s3cret", user.password)
    assert user.active
    assert user.has_role(RoleEnum.ADMIN.name)
    assert user.profile.profile_label == "Administrator"


def test_no_email_no_admin(config):
    config["BOOTSTRAP_ADMIN_EMAIL"] = ""
    bootstrap_admin()
    assert admins() == []


def test_password_must_be_a_string(config):
    config["BOOTSTRAP_ADMIN_PASSWORD"] = 123456
    with pytest.raises(TypeError, match="@str"):
        bootstrap_admin()
