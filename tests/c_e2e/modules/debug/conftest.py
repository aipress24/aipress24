# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Fixtures for debug module E2E tests.

Debug tests use fresh_db (drop/create) to ensure database tables exist,
since these tests may run after other modules that use fresh_db and
dispose connections.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


@pytest.fixture(autouse=True)
def db_session(fresh_db) -> Session:
    """Override modules/conftest.py db_session to use fresh_db.

    Debug tests use the fresh_db (drop/create) approach to ensure
    database tables exist.
    """
    return fresh_db.session
