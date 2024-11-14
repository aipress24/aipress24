# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from flask import g
from flask_sqlalchemy import SQLAlchemy
from svcs.flask import container

from app.services.sessions import SessionService


class FakeUser:
    id = 1
    is_authenticated = True


def test_session_with_authenticated_user(db: SQLAlchemy) -> None:
    g.user = FakeUser()

    session_service = container.get(SessionService)
    assert session_service.get("foo", None) is None

    session_service.set("foo", "bar")
    assert session_service.get("foo") == "bar"
