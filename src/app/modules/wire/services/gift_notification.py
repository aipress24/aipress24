# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Ticket #0194 — notify each beneficiary of a CONSULTATION_GIFT
purchase once it reaches PAID.

Triggered from the Stripe webhook (`_record_article_purchase_from_checkout`)
after the parent `ArticlePurchase` is flipped to PAID. Each beneficiary
gets :

- an in-app cloche notification linking to the article ;
- an email with the giver's name and the article link.

Side-effect failures are reported to Sentry via `report_failure` but
never raise — the payment is recorded ; the notification is best-effort.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from svcs.flask import container

from app.flask.extensions import db
from app.flask.routing import url_for
from app.lib.base62 import base62
from app.logging import report_failure
from app.models.auth import User
from app.modules.wire.models import (
    ArticlePurchase,
    ArticlePurchaseGift,
    PurchaseProduct,
)
from app.services.notifications import NotificationService

if TYPE_CHECKING:
    pass


def notify_gift_beneficiaries(purchase_id: int) -> int:
    """Send cloche + email to every beneficiary of a CONSULTATION_GIFT
    purchase. Returns the number of beneficiaries actually notified.

    Idempotent : the gift row's `notified_at` is stamped on success,
    so a webhook retry won't re-spam recipients.
    """
    purchase = db.session.get(ArticlePurchase, purchase_id)
    if purchase is None:
        return 0
    if purchase.product_type != PurchaseProduct.CONSULTATION_GIFT:
        return 0

    post = purchase.post
    if post is None:
        return 0
    giver = db.session.get(User, purchase.owner_id)
    if giver is None:
        return 0

    gifts = list(
        db.session.query(ArticlePurchaseGift).filter_by(purchase_id=purchase.id)
    )
    if not gifts:
        return 0

    article_title = getattr(post, "title", "") or getattr(post, "titre", "") or "—"
    article_url = _article_url(post)

    notified = 0
    for gift in gifts:
        if gift.notified_at is not None:
            continue  # already notified — skip on webhook replay
        recipient = db.session.get(User, gift.beneficiary_user_id)
        if recipient is None:
            continue

        # Only stamp `notified_at` if at least one side-effect actually
        # succeeded. A total failure (Sentry-logged but invisible to
        # the user) would otherwise mark the gift as notified and
        # prevent any future retry — the beneficiary would silently
        # get nothing.
        any_succeeded = False

        try:
            _post_in_app(recipient, article_title, giver, article_url)
            any_succeeded = True
        except Exception as exc:
            report_failure(
                f"consultation_gift: in-app notification failed "
                f"(purchase {purchase_id}, user {gift.beneficiary_user_id})",
                exc,
            )

        if recipient.email:
            try:
                _send_email(
                    recipient=recipient,
                    giver=giver,
                    article_title=article_title,
                    article_url=article_url,
                )
                any_succeeded = True
            except Exception as exc:
                report_failure(
                    f"consultation_gift: email failed "
                    f"(purchase {purchase_id}, user {gift.beneficiary_user_id})",
                    exc,
                )

        if any_succeeded:
            gift.notified_at = datetime.now(UTC)
            notified += 1

    if notified:
        db.session.flush()

    return notified


def _article_url(post) -> str:
    """Best-effort absolute URL for the article. Falls back to a
    relative path if `url_for` can't build an external URL (e.g.
    no request context)."""
    try:
        return url_for("wire.item", id=base62.encode(post.id), _external=True)
    except Exception:
        return f"/wire/item/{base62.encode(post.id)}"


def _post_in_app(
    recipient: User,
    article_title: str,
    giver: User,
    article_url: str,
) -> None:
    message = (
        f"{giver.full_name} vous offre un article à consulter : « {article_title} »."
    )
    container.get(NotificationService).post(recipient, message, url=article_url)


def _send_email(
    *,
    recipient: User,
    giver: User,
    article_title: str,
    article_url: str,
) -> None:
    # Lazy import : keeps wire layer cold-start cheap.
    from app.services.emails import ConsultationGiftMail

    mail = ConsultationGiftMail(
        sender="contact@aipress24.com",
        recipient=recipient.email,
        sender_mail=giver.email or "contact@aipress24.com",
        recipient_full_name=recipient.full_name,
        giver_full_name=giver.full_name,
        article_title=article_title,
        article_url=article_url,
    )
    mail.send()
