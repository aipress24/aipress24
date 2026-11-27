# Copyright (c) 2025-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Business Wall CLI commands.

- `flask bw suspend-overdue` — suspend BWs whose subscription has been
  PAST_DUE beyond the grace window (cron-friendly). Spec:
  local-notes/specs/finances-02.md §B.
- `flask bw reopen` — reopen BWs closed along with their Stripe
  subscription, without going through Stripe.
"""

from __future__ import annotations

from datetime import UTC, datetime

import click
from flask.cli import with_appcontext
from flask_super.cli import group
from loguru import logger
from sqlalchemy import select

from app.enums import BWStatus
from app.flask.extensions import db
from app.modules.bw.bw_activation.bw_cancellation import reopen_business_wall
from app.modules.bw.bw_activation.models import (
    BusinessWall,
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


@bw.command("reopen")
@click.argument("bw_ids", nargs=-1)
@click.option("--apply", is_flag=True, help="Reopen them. Without it, only list.")
@with_appcontext
def reopen(bw_ids: tuple[str, ...], apply: bool) -> None:
    """Reopen BWs closed along with their Stripe subscription.

    Stripe cancels test-mode subscriptions after 90 days, and the webhook
    then closes their BW. Without BW_IDS, takes every BW closed that way,
    newest first. The reopened BW has no Stripe subscription. The roles,
    partnerships and invitations deleted at closing are not restored.
    """
    stmt = (
        select(BusinessWall)
        .join(Subscription, Subscription.business_wall_id == BusinessWall.id)
        .where(BusinessWall.status == BWStatus.SUSPENDED.value)
        .where(Subscription.status == SubscriptionStatus.CANCELLED.value)
        .order_by(BusinessWall.created_at.desc())
    )
    if bw_ids:
        stmt = stmt.where(BusinessWall.id.in_(bw_ids))
    reopened = 0
    for business_wall in db.session.scalars(stmt).all():
        org = business_wall.get_organisation()
        label = f"{business_wall.id} {business_wall.bw_type} {org.name if org else '?'}"
        if not apply:
            click.echo(f"would reopen {label}")
        elif reopen_business_wall(business_wall):
            reopened += 1
            click.echo(f"reopened {label}")
        else:
            click.echo(f"skipped {label}: the organisation has another active BW")
    if apply:
        db.session.commit()
        click.echo(f"{reopened} BW(s) reopened")
