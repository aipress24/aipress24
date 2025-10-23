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

    # 2. Override Flask-Login's user loader to use our test session
    # This is necessary because the default loader uses db.session which may
    # not see uncommitted data in our test transaction

    from app.models.auth import User

    @app.login_manager.user_loader
    def load_user_from_test_session(user_id):
        """Load user from test session instead of global db.session."""
        return db_session.query(User).get(int(user_id))

    # 3. Create a test client
    client = app.test_client()

    # 4. Manually set up Flask-Login session to authenticate the user
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

    # 5. Yield the prepared client to the test
    return client

    # 6. The client is automatically cleaned up after the test
