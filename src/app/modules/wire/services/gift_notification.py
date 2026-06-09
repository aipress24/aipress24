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
from typing import TYPE_CHECKING, Any

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

# Marker for missing labels.
_MISSING_LABEL = "—"


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

    article_title = _extract_article_title(post)
    article_url = _article_url(post)

    notified = 0
    for gift in gifts:
        if gift.notified_at is not None:
            continue  # already notified — skip on webhook replay
        recipient = db.session.get(User, gift.beneficiary_user_id)
        if recipient is None:
            continue

        succeeded = _notify_one_gift(
            recipient=recipient,
            giver=giver,
            article_title=article_title,
            article_url=article_url,
            purchase_id=purchase_id,
            beneficiary_user_id=gift.beneficiary_user_id,
        )

        stamp = _decide_notified_at(succeeded)
        if stamp is not None:
            gift.notified_at = stamp
            notified += 1

    if notified:
        db.session.flush()

    return notified


def _decide_notified_at(succeeded_count: int) -> datetime | None:
    """Pure : the `notified_at` timestamp to stamp on the gift row iff
    at least one side-effect succeeded.

    A total failure (Sentry-logged but invisible to the user) would
    otherwise mark the gift as notified and prevent any future retry —
    the beneficiary would silently get nothing.
    """
    return datetime.now(UTC) if succeeded_count > 0 else None


def _notify_one_gift(
    *,
    recipient: User,
    giver: User,
    article_title: str,
    article_url: str,
    purchase_id: int,
    beneficiary_user_id: int,
    in_app: Any = None,
    email: Any = None,
) -> int:
    """Run both side-effects for a single beneficiary, returning the
    number that succeeded (0, 1 or 2).

    `in_app` and `email` are optional injected callables — production
    leaves them at None and uses the module-level shells. Tests can
    pass plain callables that raise / no-op without touching mail or
    the notification service.

    Failures are reported to Sentry but never raised.
    """
    in_app_call = in_app if in_app is not None else _post_in_app
    email_call = email if email is not None else _send_email

    succeeded = 0
    try:
        in_app_call(recipient, article_title, giver, article_url)
        succeeded += 1
    except Exception as exc:
        report_failure(
            f"consultation_gift: in-app notification failed "
            f"(purchase {purchase_id}, user {beneficiary_user_id})",
            exc,
        )

    if recipient.email:
        try:
            email_call(
                recipient=recipient,
                giver=giver,
                article_title=article_title,
                article_url=article_url,
            )
            succeeded += 1
        except Exception as exc:
            report_failure(
                f"consultation_gift: email failed "
                f"(purchase {purchase_id}, user {beneficiary_user_id})",
                exc,
            )

    return succeeded


def _extract_article_title(post: Any) -> str:
    """Pure : pick the article's display title with a marker fallback."""
    title = getattr(post, "title", "") or getattr(post, "titre", "")
    return title or _MISSING_LABEL


def _format_gift_message(*, article_title: str, giver_full_name: str) -> str:
    """Pure : the in-app cloche message text."""
    return f"{giver_full_name} vous offre un article à consulter : « {article_title} »."


def _relative_article_url(post_id: int) -> str:
    """Pure fallback : URL when `url_for` can't build an external one
    (e.g. no request context, no SERVER_NAME)."""
    return f"/wire/item/{base62.encode(post_id)}"


def _article_url(post) -> str:
    """Best-effort absolute URL for the article. Falls back to a
    relative path if `url_for` can't build an external URL (e.g.
    no request context)."""
    try:
        return url_for("wire.item", id=base62.encode(post.id), _external=True)
    except Exception:
        return _relative_article_url(post.id)


def _post_in_app(
    recipient: User,
    article_title: str,
    giver: User,
    article_url: str,
) -> None:
    message = _format_gift_message(
        article_title=article_title,
        giver_full_name=giver.full_name,
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
