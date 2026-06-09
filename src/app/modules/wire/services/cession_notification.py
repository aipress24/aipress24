# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Ticket #0196 — notify the buyer after a PAID CESSION purchase.

Two side-effects, both belt-and-suspenders so a failure of one doesn't
prevent the other :

- in-app cloche notification (`NotificationService.post`) ;
- email (`CessionPurchaseAcknowledgmentMail`).

Called from the Stripe webhook (`_record_article_purchase_from_checkout`)
once `ArticlePurchase.status` is PAID. Failures are sent to Sentry via
`report_failure` — never silent — but never raise back to the webhook
either (the payment is recorded ; the notification is best-effort).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from svcs.flask import container

from app.flask.extensions import db
from app.flask.routing import url_for
from app.logging import report_failure
from app.models.auth import User
from app.models.organisation import Organisation
from app.modules.wire.models import ArticlePurchase
from app.services.notifications import NotificationService

if TYPE_CHECKING:
    pass


def notify_cession_purchase(purchase_id: int) -> None:
    """Send cloche + email acknowledgment for a CESSION purchase.

    Called inline from the webhook after PAID is committed. Idempotency
    is guaranteed upstream by `stripe_checkout_session_id` uniqueness ;
    this helper never re-checks the DB beyond loading the row.
    """
    purchase = db.session.get(ArticlePurchase, purchase_id)
    if purchase is None:
        return
    buyer = db.session.get(User, purchase.owner_id)
    post = purchase.post
    if buyer is None or post is None:
        return

    author = db.session.get(User, post.owner_id)
    author_full_name = author.full_name if author is not None else "—"

    media_name = _author_media_name(author)
    amount_ht_eur = f"{(purchase.amount_cents or 0) / 100:.2f}"
    article_title = getattr(post, "title", "") or getattr(post, "titre", "") or "—"

    try:
        _post_in_app(buyer, article_title, author_full_name, media_name)
    except Exception as exc:
        report_failure(
            f"cession_purchase: in-app notification failed (purchase {purchase_id})",
            exc,
        )

    if buyer.email:
        try:
            _send_email(
                buyer=buyer,
                article_title=article_title,
                author_full_name=author_full_name,
                media_name=media_name,
                amount_ht_eur=amount_ht_eur,
            )
        except Exception as exc:
            report_failure(
                f"cession_purchase: email failed (purchase {purchase_id})",
                exc,
            )


def _author_media_name(author: User | None) -> str:
    """Best-effort « organe de presse » label for the author."""
    if author is None:
        return "—"
    org = author.organisation
    if org is None and author.organisation_id:
        org = db.session.get(Organisation, author.organisation_id)
    if org is None:
        return "—"
    return getattr(org, "bw_name", None) or getattr(org, "name", "") or "—"


def _post_in_app(
    buyer: User,
    article_title: str,
    author_full_name: str,
    media_name: str,
) -> None:
    message = (
        f"Vous venez d'acquérir les droits de reproduction de "
        f"« {article_title} » de {author_full_name} ({media_name})."
    )
    try:
        post_url = url_for("wip.achats")
    except Exception:
        post_url = "/wip/achats"
    container.get(NotificationService).post(buyer, message, url=post_url)


def _send_email(
    *,
    buyer: User,
    article_title: str,
    author_full_name: str,
    media_name: str,
    amount_ht_eur: str,
) -> None:
    # Lazy import : keeps the wire layer from pulling the full mailer
    # bundle into its cold-start path.
    from app.services.emails import CessionPurchaseAcknowledgmentMail

    mail = CessionPurchaseAcknowledgmentMail(
        sender="contact@aipress24.com",
        recipient=buyer.email,
        sender_mail="contact@aipress24.com",
        article_title=article_title,
        author_full_name=author_full_name,
        media_name=media_name,
        amount_ht_eur=amount_ht_eur,
    )
    mail.send()
