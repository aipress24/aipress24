# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Unit tests for database URL extraction and enforcing psycopg v3 use."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.flask.config import get_db_url

DB_URL_VARS = (
    "FLASK_SQLALCHEMY_DATABASE_URI",
    "SQLALCHEMY_DATABASE_URI",
    "DATABASE_URL",
    "POSTGRESQL_ADDON_URI",
)


@pytest.fixture(autouse=True)
def _clear_db_url_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep the developer's shell from overriding the URL a test sets."""
    for var in DB_URL_VARS:
        monkeypatch.delenv(var, raising=False)


class TestGetDbUrl:
    def test_normalizes_postgres_prefix(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv(
            "DATABASE_URL", "postgres://user:secret@db.example.com:5432/myapp"
        )
        url = get_db_url(MagicMock())
        assert url == "postgresql+psycopg://user:secret@db.example.com:5432/myapp"

    def test_normalizes_postgresql_prefix(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv(
            "DATABASE_URL", "postgresql://user:secret@localhost:5432/myapp"
        )
        url = get_db_url(MagicMock())
        assert url == "postgresql+psycopg://user:secret@localhost:5432/myapp"

    def test_normalizes_legacy_psycopg2_prefix(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv(
            "FLASK_SQLALCHEMY_DATABASE_URI",
            "postgresql+psycopg2://user:secret@localhost:5432/myapp",
        )
        url = get_db_url(MagicMock())
        assert url == "postgresql+psycopg://user:secret@localhost:5432/myapp"

    def test_preserves_postgresql_psycopg_prefix(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv(
            "FLASK_SQLALCHEMY_DATABASE_URI",
            "postgresql+psycopg://user:secret@localhost:5432/myapp",
        )
        url = get_db_url(MagicMock())
        assert url == "postgresql+psycopg://user:secret@localhost:5432/myapp"

    def test_preserves_sqlite_url(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("DATABASE_URL", "sqlite:////tmp/test.db")
        url = get_db_url(MagicMock())
        assert url == "sqlite:////tmp/test.db"

    def test_precedence_flask_over_heroku(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv(
            "FLASK_SQLALCHEMY_DATABASE_URI", "postgresql+psycopg://local/custom"
        )
        monkeypatch.setenv("DATABASE_URL", "postgres://remote/heroku")
        url = get_db_url(MagicMock())
        assert url == "postgresql+psycopg://local/custom"

    def test_unprefixed_sqlalchemy_database_uri(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv(
            "SQLALCHEMY_DATABASE_URI",
            "postgresql://user:secret@localhost:5432/myapp",
        )
        url = get_db_url(MagicMock())
        assert url == "postgresql+psycopg://user:secret@localhost:5432/myapp"

    def test_normalizes_app_config_fallback(self, monkeypatch: pytest.MonkeyPatch):
        app = MagicMock()
        app.config = {"SQLALCHEMY_DATABASE_URI": "postgresql://localhost/from_secrets"}
        url = get_db_url(app)
        assert url == "postgresql+psycopg://localhost/from_secrets"

    def test_empty_when_no_env_and_no_config(self, monkeypatch: pytest.MonkeyPatch):
        app = MagicMock()
        app.config = {}
        url = get_db_url(app)
        assert url == ""
