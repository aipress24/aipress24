# Copyright (c) 2025-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Stripe CLI commands.

Three command groups:

- `flask stripe verify <resource>` — read-only drift detection (exits
  non-zero if any drift is found ; cron-friendly).
- `flask stripe sync <resource>` — manual write-side correction
  (pulls canonical state from Stripe and updates the local mirror).
- `flask stripe simulate-checkout <bw_id>` — dev/test only, fires a
  fake `checkout.session.completed` through the live handler.

The legacy command `flask stripe reconcile` is preserved as an alias of
`flask stripe verify subscriptions`. Spec: local-notes/specs/finances.md §9.
"""

from __future__ import annotations

import os
import sys
import uuid
from collections.abc import Callable
from types import SimpleNamespace

import click
from flask.cli import with_appcontext
from flask_super.cli import group
from loguru import logger
from sqlalchemy import select
from svcs.flask import container

from app.flask.extensions import db
from app.models.organisation import Organisation
from app.services.emails import EmailService
from app.services.stripe.customers import mirror_customer_to_org
from app.services.stripe.prices import list_drifts, sync_all_prices
from app.services.stripe.reconciliation import (
    reconcile_customers,
    reconcile_purchases,
    reconcile_subscriptions,
)
from app.services.stripe.retriever import retrieve_customer
from app.services.stripe.utils import load_stripe_api_key

# Resource name → drift-listing function. Single source of truth for
# `verify <resource>` and `verify all`. Each function returns a list of
# dataclass instances; an empty list means "no drift".
VERIFIERS: dict[str, Callable[[], list]] = {
    "prices": list_drifts,
    "customers": reconcile_customers,
    "subscriptions": reconcile_subscriptions,
    "purchases": reconcile_purchases,
}


@group(short_help="Stripe integration tooling")
def stripe() -> None:
    """Stripe integration utilities."""


# ---------------------------------------------------------------------------
# verify — read-only drift detection
# ---------------------------------------------------------------------------


@stripe.group()
def verify() -> None:
    """Detect drift between local mirror and Stripe (read-only)."""


@verify.command("prices")
@with_appcontext
def verify_prices() -> None:
    """Compare local `stripe_price` rows with Stripe."""
    _report_drifts("prices", VERIFIERS["prices"]())


@verify.command("subscriptions")
@with_appcontext
def verify_subscriptions() -> None:
    """Compare local `Subscription` rows with Stripe."""
    _report_drifts("subscriptions", VERIFIERS["subscriptions"]())


@verify.command("customers")
@with_appcontext
def verify_customers() -> None:
    """Compare `Organisation.stripe_customer_id` rows with Stripe."""
    _report_drifts("customers", VERIFIERS["customers"]())


@verify.command("purchases")
@with_appcontext
def verify_purchases() -> None:
    """Compare recent `ArticlePurchase` rows with Stripe checkout sessions."""
    _report_drifts("purchases", VERIFIERS["purchases"]())


@verify.command("all")
@with_appcontext
def verify_all() -> None:
    """Run every verify command sequentially. Exit non-zero on any drift."""
    failures: list[str] = []
    for name, fn in VERIFIERS.items():
        drifts = fn()
        if drifts:
            failures.append(name)
            _report_drifts(name, drifts, exit_on_drift=False)
        else:
            click.echo(f"✓ {name}: no drift")

    if failures:
        click.echo(f"Drift detected in: {', '.join(failures)}.", err=True)
        sys.exit(1)


# ---------------------------------------------------------------------------
# sync — manual correction
# ---------------------------------------------------------------------------


@stripe.group()
def sync() -> None:
    """Push state from Stripe into the local mirror (write-side, manual)."""


@sync.command("prices")
@with_appcontext
def sync_prices() -> None:
    """Re-sync every active Stripe Price into `stripe_price`."""
    n = sync_all_prices()
    click.echo(f"Synced {n} active price(s) from Stripe.")


@sync.command("customers")
@with_appcontext
def sync_customers() -> None:
    """Re-sync each bound Organisation's billing identity (email, VAT,
    address) from its Stripe Customer. Spec: finances-02 §C."""
    if not load_stripe_api_key():
        click.echo("Stripe API key not configured; skipping.")
        return
    orgs = db.session.scalars(
        select(Organisation).where(Organisation.stripe_customer_id.is_not(None))
    ).all()
    synced = 0
    for org in orgs:
        customer = retrieve_customer(org.stripe_customer_id, expand=["tax_ids"])
        if customer is None or getattr(customer, "deleted", False):
            continue
        mirror_customer_to_org(org, customer)
        synced += 1
    if synced:
        db.session.commit()
    click.echo(f"Synced billing for {synced} organisation(s) from Stripe.")


# ---------------------------------------------------------------------------
# Legacy `reconcile` — kept as an alias of `verify subscriptions`.
# ---------------------------------------------------------------------------


@stripe.command()
@with_appcontext
def reconcile() -> None:
    """Deprecated. Use `flask stripe verify subscriptions` instead."""
    click.echo(
        "Note: `flask stripe reconcile` is now an alias of "
        "`flask stripe verify subscriptions`. Switch to the new name.",
        err=True,
    )
    _report_drifts("subscriptions", VERIFIERS["subscriptions"]())


# ---------------------------------------------------------------------------
# simulate-checkout — dev helper
# ---------------------------------------------------------------------------


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
        f"(session={session_id}, bw={bw_id}).",
    )


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------


def _report_drifts(name: str, drifts, *, exit_on_drift: bool = True) -> None:
    """Log drifts, optionally exit non-zero, email an admin if `CRON_RUN=1`."""
    if not drifts:
        click.echo(f"✓ {name}: no drift")
        return

    for d in drifts:
        logger.warning("{} drift: {}", name, d)

    click.echo(f"{len(drifts)} drift(s) in {name}; see logs.", err=True)
    if os.environ.get("CRON_RUN") == "1":
        _send_drift_email(name, drifts)
    if exit_on_drift:
        sys.exit(1)


def _send_drift_email(name: str, drifts) -> None:
    """Notify the admin recipients defined in `EmailService` on drift."""
    body_lines = [f"Drift detected on Stripe mirror for: {name}.", ""]
    body_lines.extend(f"  {d}" for d in drifts)
    container.get(EmailService).send_system_email(
        msg="\n".join(body_lines),
        subject=f"[Aipress24] Stripe drift on {name}",
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
