# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""
Splinter tests.

These tests need a database with some fake data and/or a real config
(i.e. don't work with the testing config)
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from splinter import Browser

from app.flask.main import create_app

if TYPE_CHECKING:
    from flask import Flask


class Config:
    SECRET_KEY = "changeme"  # noqa: S105
    SECURITY_PASSWORD_SALT = "changeme"  # noqa: S105
    DEBUG = False
    DEBUG_TB_ENABLED = False

    SQLALCHEMY_DATABASE_URI = "postgresql://localhost/aipress24"
    # SQLALCHEMY_DATABASE_URI = "postgresql://localhost/aipress24_test"


@pytest.fixture(scope="session")
def app() -> Flask:
    app = create_app(Config())
    return app


@pytest.fixture(scope="module")
def browser(app) -> Browser:
    return Browser("flask", app=app)
