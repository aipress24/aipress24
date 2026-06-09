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

from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from svcs.flask import container

from app.flask.extensions import db
from app.flask.routing import url_for
from app.logging import report_failure
from app.models.auth import User
from app.models.organisation import Organisation
from app.modules.wire.models import ArticlePurchase, PurchaseStatus
from app.services.notifications import NotificationService

if TYPE_CHECKING:
    pass

# Marker used everywhere when a label can't be resolved.
_MISSING_LABEL = "—"


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
    if not _should_notify_cession(purchase, buyer, post):
        return

    author = db.session.get(User, post.owner_id)
    media_name = _author_media_name(author)
    ctx = _build_purchase_context(
        purchase=purchase, post=post, author=author, media_name=media_name
    )

    try:
        _post_in_app(
            buyer,
            ctx["article_title"],
            ctx["author_full_name"],
            ctx["media_name"],
        )
    except Exception as exc:
        report_failure(
            f"cession_purchase: in-app notification failed (purchase {purchase_id})",
            exc,
        )

    if buyer.email:
        try:
            _send_email(
                buyer=buyer,
                article_title=ctx["article_title"],
                author_full_name=ctx["author_full_name"],
                media_name=ctx["media_name"],
                amount_ht_eur=ctx["amount_ht_eur"],
            )
        except Exception as exc:
            report_failure(
                f"cession_purchase: email failed (purchase {purchase_id})",
                exc,
            )


def _should_notify_cession(purchase: Any, buyer: Any, post: Any) -> bool:
    """Pure : true iff we have enough state to send the cession ack.

    The webhook commits PAID before calling us, but defensive checks
    avoid sending nonsense if upstream changes. We require:
    - a purchase row exists,
    - it's in PAID status,
    - a buyer User row was resolved,
    - the related Post is still attached.
    """
    if purchase is None or buyer is None or post is None:
        return False
    return purchase.status == PurchaseStatus.PAID


def _build_purchase_context(
    *,
    purchase: Any,
    post: Any,
    author: Any,
    media_name: str,
) -> dict[str, str]:
    """Pure : assemble the strings consumed by the in-app + email shells."""
    return {
        "article_title": _extract_article_title(post),
        "author_full_name": _author_full_name(author),
        "media_name": media_name,
        "amount_ht_eur": _format_amount_eur(getattr(purchase, "amount_cents", None)),
    }


def _extract_article_title(post: Any) -> str:
    """Pure : pick the article's display title with a marker fallback."""
    title = getattr(post, "title", "") or getattr(post, "titre", "")
    return title or _MISSING_LABEL


def _author_full_name(author: Any) -> str:
    """Pure : full name of the author, marker fallback if missing."""
    if author is None:
        return _MISSING_LABEL
    return getattr(author, "full_name", "") or _MISSING_LABEL


def _format_amount_eur(amount_cents: int | None) -> str:
    """Pure : cents → ``"%.2f"`` euros, treating None as 0."""
    return f"{(amount_cents or 0) / 100:.2f}"


def _format_cession_message(
    *, article_title: str, author_full_name: str, media_name: str
) -> str:
    """Pure : the in-app cloche message text."""
    return (
        f"Vous venez d'acquérir les droits de reproduction de "
        f"« {article_title} » de {author_full_name} ({media_name})."
    )


def _org_media_label(org: Any | None) -> str:
    """Pure : best-effort « organe de presse » label for an Organisation."""
    if org is None:
        return _MISSING_LABEL
    return getattr(org, "bw_name", None) or getattr(org, "name", "") or _MISSING_LABEL


def _author_media_name(
    author: Any | None,
    *,
    org_loader: Callable[[int], Any | None] | None = None,
) -> str:
    """Best-effort « organe de presse » label for the author.

    `org_loader` is the optional DB fallback used when the author's
    `organisation` relationship hasn't been hydrated but we still have
    an `organisation_id`. Defaults to `db.session.get(Organisation, …)`
    in production. Tests pass their own loader and never touch the
    session.
    """
    if author is None:
        return _MISSING_LABEL
    org = getattr(author, "organisation", None)
    if org is None and getattr(author, "organisation_id", None):
        loader = org_loader or _default_org_loader
        org = loader(author.organisation_id)
    return _org_media_label(org)


def _default_org_loader(org_id: int) -> Any | None:
    """Production loader : `db.session.get(Organisation, org_id)`."""
    return db.session.get(Organisation, org_id)


def _post_in_app(
    buyer: User,
    article_title: str,
    author_full_name: str,
    media_name: str,
) -> None:
    message = _format_cession_message(
        article_title=article_title,
        author_full_name=author_full_name,
        media_name=media_name,
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
