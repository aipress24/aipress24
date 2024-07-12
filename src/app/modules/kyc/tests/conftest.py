# Copyright (c) 2021-2024 - Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-onlyfrom __future__ import annotations

# ruff: noqa: E402
from __future__ import annotations

import contextlib
from collections.abc import Iterator
from typing import Any

import pytest
from flask import Flask
from flask.ctx import AppContext
from flask.testing import FlaskClient
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, scoped_session

from app.flask.main import create_app


class TestConfig:
    SECRET_KEY = "test_secret"
    WTF_CSRF_SECRET_KEY = "csrf secret"
    DBPATH = ""
    SQLALCHEMY_DATABASE_URI = "sqlite://"


def cleanup_db(db: SQLAlchemy) -> None:
    """Drop all the tables, in a way that doesn't raise integrity errors."""

    for table in reversed(db.metadata.sorted_tables):
        with contextlib.suppress(SQLAlchemyError):
            db.session.execute(table.delete())


@pytest.fixture
def config() -> Any:
    return TestConfig


@pytest.fixture
def app(config: Any) -> Flask:
    return create_app(config=config)


@pytest.fixture
def app_context(app) -> AppContext:
    with app.app_context() as ctx:
        yield ctx


@pytest.fixture
def db(app_context: AppContext, app: Flask) -> Iterator[SQLAlchemy]:
    """Return a fresh db for each test."""
    from app.flask.extensions import db as _db

    cleanup_db(_db)
    _db.create_all()
    yield _db

    _db.session.remove()
    cleanup_db(_db)


@pytest.fixture
def db_session(db: SQLAlchemy) -> Session:
    return db.session


@pytest.fixture
def client(app: Flask, db_session: scoped_session) -> FlaskClient:
    """Return a Web client, used for testing, bound to a DB session."""
    return app.test_client()
