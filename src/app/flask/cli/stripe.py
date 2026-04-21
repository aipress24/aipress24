# Copyright (c) 2025, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Stripe CLI commands for reconciliation and local dry-run.

Commands:

- `flask stripe reconcile` : compare every local Subscription with its
  Stripe state, log warnings on drift, emit a non-zero exit code if any
  drift is found (useful in cron monitoring).
- `flask stripe simulate-checkout <bw_id>` : fire a fake
  `checkout.session.completed` event through the same handler Stripe
  would call. No network hit, for local dev only.
"""

from __future__ import annotations

import sys
import uuid
from types import SimpleNamespace

import click
from flask.cli import with_appcontext
from flask_super.cli import group
from loguru import logger


@group(short_help="Stripe integration tooling")
def stripe() -> None:
    """Stripe integration utilities."""


@stripe.command()
@with_appcontext
def reconcile() -> None:
    """Compare local Subscription state with Stripe and log drifts."""
    from app.services.stripe.reconciliation import reconcile_subscriptions

    drifts = reconcile_subscriptions()
    if not drifts:
        click.echo("No drift: local and Stripe states match.")
        return

    for d in drifts:
        logger.warning(
            "Stripe drift | sub={} stripe={} issue={} local={} stripe_status={}",
            d.subscription_id,
            d.stripe_id,
            d.issue,
            d.local_status,
            d.stripe_status,
        )
    click.echo(f"{len(drifts)} drift(s) detected; see logs.", err=True)
    sys.exit(1)


@stripe.command("simulate-checkout")
@click.argument("bw_id")
@click.option(
    "--customer-id",
    default="cus_sim_local",
    help="Fake Stripe customer id to attach.",
)
@click.option(
    "--subscription-id",
    default="sub_sim_local",
    help="Fake Stripe subscription id to attach.",
)
@with_appcontext
def simulate_checkout(
    bw_id: str,
    customer_id: str,
    subscription_id: str,
) -> None:
    """Fire a fake `checkout.session.completed` for a local BW.

    Useful to validate the webhook flow without configuring the Stripe CLI.
    """
    # Validate bw_id shape early.
    try:
        uuid.UUID(bw_id)
    except (ValueError, TypeError):
        click.echo(f"Invalid BW UUID: {bw_id!r}", err=True)
        sys.exit(1)

    session_id = f"cs_sim_{uuid.uuid4().hex[:8]}"
    fake_event = _build_fake_event(
        session_id=session_id,
        bw_id=bw_id,
        customer_id=customer_id,
        subscription_id=subscription_id,
    )

    from app.modules.stripe.views.webhook import on_checkout_session_completed

    on_checkout_session_completed(fake_event)
    click.echo(
        f"Dispatched fake checkout.session.completed "
        f"(session={session_id}, bw={bw_id})."
    )


def _build_fake_event(
    *,
    session_id: str,
    bw_id: str,
    customer_id: str,
    subscription_id: str,
) -> SimpleNamespace:
    data_obj = {
        "id": session_id,
        "mode": "subscription",
        "client_reference_id": bw_id,
        "customer": customer_id,
        "subscription": subscription_id,
        "payment_status": "paid",
        "metadata": {},
    }
    return SimpleNamespace(
        id=f"evt_{session_id}",
        type="checkout.session.completed",
        data=SimpleNamespace(object=data_obj),
    )
