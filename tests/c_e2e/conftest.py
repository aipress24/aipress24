# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""E2E tests configuration.

These tests use the shared app fixture from tests/conftest.py and Flask's test client.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import TYPE_CHECKING

import pytest

from .utils import create_stuff

if TYPE_CHECKING:
    from flask import Flask
    from flask.testing import FlaskClient
    from sqlalchemy.orm import Session


@pytest.fixture
def logged_in_client(app: Flask, db_session: Session) -> Iterator[FlaskClient]:
    """
    Provides a logged-in Flask test client for a single test function.

    This fixture ensures each test runs in isolation with a clean database state
    and an authenticated user.
    """
    # 1. Create necessary data for the test
    user_data = create_stuff(db_session)
    user = user_data["user"]

    # 2. Create a test client
    client = app.test_client()

    # 3. Manually set up Flask-Login session to authenticate the user
    with client.session_transaction() as sess:
        # Flask-Login stores the user ID in this key
        sess["_user_id"] = str(user.id)
        # Mark session as fresh (recently authenticated)
        sess["_fresh"] = True
        # Make session permanent
        sess["_permanent"] = True
        # Flask-Security specific keys
        sess["_id"] = (
            str(user.fs_uniquifier) if hasattr(user, "fs_uniquifier") else str(user.id)
        )

    # 4. Yield the prepared client to the test
    return client

    # 5. The client is automatically cleaned up after the test
