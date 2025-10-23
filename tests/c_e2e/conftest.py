# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""E2E tests configuration.

These tests use the shared app fixture from tests/conftest.py and Flask's test client.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from .utils import create_stuff, login

if TYPE_CHECKING:
    from flask import Flask
    from flask.testing import FlaskClient
    from sqlalchemy.orm import Session


@pytest.fixture
def logged_in_client(app: Flask, db_session: Session) -> FlaskClient:
    """
    Provides a logged-in Flask test client for a single test function.

    This fixture ensures each test runs in isolation with a clean database state
    and an authenticated user.
    """
    # 1. Create necessary data for the test
    create_stuff(db_session)

    # 2. Create a test client
    client = app.test_client()

    # 3. Log the user in using the backdoor
    login(client)

    # 4. Yield the prepared client to the test
    return client

    # 5. The client is automatically cleaned up after the test
