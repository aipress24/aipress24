# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Shared fixtures for modules E2E tests.

These tests use transaction wrapping (savepoints) for isolation,
which is more efficient than fresh_db for tests that don't need
complete database reset.

Note: Individual test modules may define their own `authenticated_client`
fixture that uses make_authenticated_client() from the root conftest.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


@pytest.fixture(autouse=True)
def db_session(fresh_db) -> Session:
    """Override modules/conftest.py db_session to use fresh_db.

    Wire tests use the fresh_db (drop/create) approach rather than
    transaction wrapping.
    """
    return fresh_db.session
