# Copyright (c) 2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""The `flask roles list` and `flask users list` commands."""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.models.auth import Role, User

if TYPE_CHECKING:
    from flask import Flask
    from sqlalchemy.orm import Session


def test_roles_list_shows_roles(app: Flask, db_session: Session) -> None:
    db_session.add(Role(name="CLI_TEST_ROLE", description="For the CLI test"))
    db_session.flush()

    result = app.test_cli_runner().invoke(args=["roles", "list"])

    assert result.exit_code == 0, result.output
    assert "CLI_TEST_ROLE" in result.output


def test_users_list_shows_active_users_only(app: Flask, db_session: Session) -> None:
    db_session.add_all(
        [
            User(email="active-cli@example.com", active=True),
            User(email="inactive-cli@example.com", active=False),
        ]
    )
    db_session.flush()

    result = app.test_cli_runner().invoke(args=["users", "list"])

    assert result.exit_code == 0, result.output
    assert "active-cli@example.com" in result.output
    assert "inactive-cli@example.com" not in result.output
    assert "Total: 1 users" in result.output
