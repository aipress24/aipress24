# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Fixtures for wire module E2E tests.

Wire tests use fresh_db (drop/create) instead of the transaction-wrapping
approach from modules/conftest.py. This db_session override ensures
compatibility.
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
    yield fresh_db.session
