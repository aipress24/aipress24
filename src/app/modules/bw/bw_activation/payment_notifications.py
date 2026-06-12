# Copyright (c) 2025-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Dunning notification for failed subscription payments (finances-02 §B)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from loguru import logger

from app.flask.extensions import db
from app.models.auth import User
from app.modules.bw.bw_activation.subscription_lifecycle import SUBSCRIPTION_GRACE_DAYS
from app.services.emails import BWPaymentFailedMail

if TYPE_CHECKING:
    from app.modules.bw.bw_activation.models import Subscription


def notify_bw_payment_failed(sub: Subscription) -> None:
    """Send a dunning reminder to the BW owner.

    Best-effort: returns quietly on any missing data. Callers should still
    guard against transport errors (the webhook wraps this in try/except so
    a mail failure never blocks event processing).
    """
    bw = sub.business_wall
    if bw is None or not bw.owner_id:
        return
    owner = db.session.get(User, bw.owner_id)
    if owner is None or not owner.email:
        return

    bw_name = getattr(bw, "name_safe", None) or bw.name or "votre Business Wall"
    mail = BWPaymentFailedMail(
        sender="contact@aipress24.com",
        recipient=owner.email,
        sender_mail="contact@aipress24.com",
        bw_name=bw_name,
        grace_days=SUBSCRIPTION_GRACE_DAYS,
    )
    mail.send()
    logger.info(f"dunning mail sent to {owner.email} for BW {bw.id}")
