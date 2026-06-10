# Copyright (c) 2021-2026, Abilian SAS & TCA
# SPDX-License-Identifier: AGPL-3.0-only

"""Unit-tier conftest : override the autouse db_session fixture to
SKIP the heavy DB-session setup (connection + savepoint creation)
while still pushing a Flask app context — many « unit » tests need
the app context for `current_app`, `url_for`, `g`, etc., even when
they don't touch the DB.

Real DB round-trips belong at tests/b_integration/. If any test
under tests/a_unit/ legitimately needs a session, it should be
relocated.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest


@pytest.fixture(autouse=True)
def db_session(app: Any) -> Iterator[None]:
    """Lightweight override : push app context, skip DB plumbing."""
    ctx = app.app_context()
    ctx.push()
    try:
        yield None
    finally:
        ctx.pop()
