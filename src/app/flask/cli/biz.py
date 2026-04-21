# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Marketplace CLI commands.

- `flask biz close-expired` : flips any OPEN offer whose `deadline`
  (or `starting_date` for jobs) is in the past to `CLOSED`. Safe to
  run on a nightly cron. Prints a count summary, exit code 0.
"""

from __future__ import annotations

import click
from flask.cli import with_appcontext
from flask_super.cli import group


@group(short_help="Marketplace tooling")
def biz() -> None:
    """Marketplace (biz) utilities."""


@biz.command("close-expired")
@with_appcontext
def close_expired() -> None:
    """Mark every expired OPEN offer as CLOSED."""
    from app.modules.biz.services.auto_close import close_expired_offers

    result = close_expired_offers()
    click.echo(
        f"Auto-close run: missions={result['missions']}, "
        f"projects={result['projects']}, jobs={result['jobs']} "
        f"(total={sum(result.values())})"
    )
