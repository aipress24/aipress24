# Copyright (c) 2025-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Pure subscription-lifecycle transitions on Stripe payment events.

Functional core (no IO, no DB) for the auto-suspend / reactivate flow
specified in `local-notes/specs/finances-02.md` §B. The imperative shell
(webhook handlers, nightly job) lives in the stripe webhook view and the
`flask bw` CLI ; it calls these to decide the next state, then applies it.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from app.modules.bw.bw_activation.models import BWStatus, SubscriptionStatus

# Days a subscription may stay PAST_DUE before its BW is suspended. The
# window covers Stripe's own dunning retries so we never suspend a BW that
# Stripe is still trying to collect from.
SUBSCRIPTION_GRACE_DAYS = 7


def mark_past_due(
    current_status: str, past_due_since: datetime | None, now: datetime
) -> tuple[str, datetime]:
    """A failed invoice → subscription PAST_DUE.

    Idempotent: a replayed `invoice.payment_failed` keeps the original
    `past_due_since` so the grace window is measured from the *first*
    failure, not the latest retry.
    """
    return SubscriptionStatus.PAST_DUE.value, past_due_since or now


def clear_past_due(current_status: str, bw_status: str) -> tuple[str, str]:
    """A succeeded invoice → subscription ACTIVE again.

    A BW that was suspended for non-payment is reactivated. Any other BW
    status is left untouched (a CANCELLED BW does not silently come back).
    Returns `(subscription_status, bw_status)`.
    """
    new_bw_status = (
        BWStatus.ACTIVE.value if bw_status == BWStatus.SUSPENDED.value else bw_status
    )
    return SubscriptionStatus.ACTIVE.value, new_bw_status


def is_recovery_needed(current_status: str, past_due_since: datetime | None) -> bool:
    """True when a payment success should trigger a state change.

    A normal renewal (already ACTIVE, never been past-due) needs nothing.
    """
    return (
        current_status != SubscriptionStatus.ACTIVE.value or past_due_since is not None
    )


def _naive(dt: datetime) -> datetime:
    """Drop tzinfo so a tz-aware webhook stamp and a tz-naive DB read (the
    `past_due_since` column is naive) compare cleanly. Everything is UTC."""
    return dt.replace(tzinfo=None) if dt.tzinfo is not None else dt


def is_overdue(
    current_status: str,
    past_due_since: datetime | None,
    now: datetime,
    grace_days: int = SUBSCRIPTION_GRACE_DAYS,
) -> bool:
    """True when a PAST_DUE subscription has exceeded the grace window and
    its BW should now be suspended."""
    if current_status != SubscriptionStatus.PAST_DUE.value or past_due_since is None:
        return False
    return _naive(past_due_since) <= _naive(now) - timedelta(days=grace_days)
