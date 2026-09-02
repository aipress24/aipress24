# Copyright (c) 2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Cron actor: catch-up sync of the Stripe price and product mirrors.

Live mirroring happens via webhooks (`price.*` and `product.*`, see
``app.modules.stripe.views.webhook``). This hourly job is the safety
net — it re-pulls both catalogues in case an event was dropped (endpoint
down, Stripe retry exhausted, a change made before the webhook existed).

It repairs rather than reports, like the search rebuild actor: a mirror
that has silently drifted is one where the article page shows a stale
price or none at all, and a log line nobody reads would not fix that.
``flask stripe verify prices|products`` stays the read-only view for a
human who wants to inspect without writing.

It is also what bootstraps a fresh deployment, which is why nothing
syncs at import or on first request: startup must not depend on Stripe
being reachable, and N workers racing to fetch the same catalogue is not
a bootstrap, it is a thundering herd.

Runs at HH:30, clear of the reputation actor at HH:00 and the search
rebuild at HH:15.
"""

from __future__ import annotations

import time

from loguru import logger

from app.dramatiq.scheduler import crontab
from app.services.stripe.prices import sync_all_prices
from app.services.stripe.product_mirror import sync_all_products
from app.services.stripe.utils import load_stripe_api_key


@crontab("30 * * * *")
def sync_stripe_mirrors() -> None:
    if not load_stripe_api_key():
        logger.info("cron: stripe mirrors skipped — no API key configured")
        return

    logger.info("cron: stripe mirror sync starting")
    started = time.monotonic()
    prices = sync_all_prices()
    products = sync_all_products()
    elapsed = time.monotonic() - started
    logger.info(
        "cron: stripe mirror sync done in {:.1f}s — {} price(s), {} product(s)",
        elapsed,
        prices,
        products,
    )
