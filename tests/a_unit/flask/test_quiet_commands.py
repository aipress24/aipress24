# Copyright (c) 2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Only one-shot `flask` commands lose their logs and Sentry, never a service."""

from __future__ import annotations

import pytest

from app.flask.config import is_quiet_command

FLASK = "/app/src/.venv/bin/flask"


@pytest.mark.parametrize(
    ("argv", "quiet"),
    [
        ([FLASK, "db", "upgrade"], True),
        ([FLASK, "test-email"], True),
        ([FLASK, "queue", "scheduler"], False),
        ([FLASK, "--app", "wsgi", "queue", "scheduler"], False),
        (["/usr/lib/python/site-packages/dramatiq/__main__.py", "entry"], False),
        (["/app/src/.venv/bin/gunicorn", "-c", "gunicorn.conf.py"], False),
    ],
)
def test_is_quiet_command(argv, quiet) -> None:
    assert is_quiet_command(argv) is quiet
