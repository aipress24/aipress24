# Copyright (c) 2021-2026, Abilian SAS & TCA
# SPDX-License-Identifier: AGPL-3.0-only

"""Unit-tier conftest : override the autouse db_session fixture to
SKIP the per-test DB-session plumbing (connection + savepoint
creation) while still :

1. pushing a Flask app context — many « unit » tests need it for
   `current_app`, `url_for`, `g`, etc.
2. depending on the session-scoped `db` fixture — that fixture calls
   `_db.create_all()` to set up the schema, which several unit tests
   silently rely on (e.g. `EmailLimiter.send()` queries `email_log`).

The `db` dependency is REQUIRED for pytest-xdist parallel execution :
without it, only workers that happen to receive a `db`-requesting
test would create the schema, and the rest would fail with
`OperationalError: no such table`.

Real DB round-trips belong at tests/b_integration/. If any test
under tests/a_unit/ legitimately needs a session, it should be
relocated.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest


@pytest.fixture(autouse=True)
def db_session(app: Any, db: Any) -> Iterator[None]:
    """Lightweight override : push app context, ensure schema exists
    (via the `db` session fixture), skip per-test savepoint plumbing."""
    ctx = app.app_context()
    ctx.push()
    try:
        yield None
    finally:
        ctx.pop()
