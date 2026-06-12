# Copyright (c) 2025-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Business Wall CLI commands.

- `flask bw suspend-overdue` — suspend BWs whose subscription has been
  PAST_DUE beyond the grace window (cron-friendly). Spec:
  local-notes/specs/finances-02.md §B.
"""

from __future__ import annotations

from datetime import UTC, datetime

import click
from flask.cli import with_appcontext
from flask_super.cli import group
from loguru import logger
from sqlalchemy import select

from app.flask.extensions import db
from app.modules.bw.bw_activation.models import (
    BWStatus,
    Subscription,
    SubscriptionStatus,
)
from app.modules.bw.bw_activation.subscription_lifecycle import (
    SUBSCRIPTION_GRACE_DAYS,
    is_overdue,
)


@group(short_help="Business Wall tooling")
def bw() -> None:
    """Business Wall maintenance utilities."""


@bw.command("suspend-overdue")
@click.option(
    "--grace-days",
    default=SUBSCRIPTION_GRACE_DAYS,
    show_default=True,
    help="Days a subscription may stay PAST_DUE before its BW is suspended.",
)
@with_appcontext
def suspend_overdue(grace_days: int) -> None:
    """Suspend BWs whose subscription is PAST_DUE beyond the grace window.

    Idempotent — a BW already suspended (or cancelled) is left alone. Meant
    to run nightly. Spec: local-notes/specs/finances-02.md §B.
    """
    now = datetime.now(UTC)
    stmt = select(Subscription).where(
        Subscription.status == SubscriptionStatus.PAST_DUE.value
    )
    suspended = 0
    for sub in db.session.scalars(stmt):
        if not is_overdue(sub.status, sub.past_due_since, now, grace_days):
            continue
        business_wall = sub.business_wall
        if business_wall is None or business_wall.status == BWStatus.SUSPENDED.value:
            continue
        business_wall.status = BWStatus.SUSPENDED.value
        suspended += 1
        logger.info(
            f"BW {business_wall.id} suspended "
            f"(subscription PAST_DUE since {sub.past_due_since})"
        )
    if suspended:
        db.session.commit()
    logger.info(f"suspend-overdue: {suspended} BW(s) suspended")
    click.echo(f"{suspended} BW(s) suspended")
