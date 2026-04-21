# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Article paywall — justificatif PDF generation (MVP v0).

Synchronous helper invoked by the Dramatiq actor (or directly in
tests). Renders an HTML template, runs WeasyPrint, stores the PDF as
a `FileObject` on the `ArticlePurchase`, and notifies the buyer.

Idempotent: a second call on a purchase that already has `pdf_file`
set is a no-op.
"""

from __future__ import annotations

from importlib import resources as rso

from flask import render_template_string
from weasyprint import HTML

from app.flask.extensions import db
from app.lib.file_object_utils import create_file_object
from app.logging import warn
from app.models.auth import User
from app.modules.wire.models import (
    ArticlePurchase,
    Post,
    PurchaseProduct,
)
from app.services.emails import JustificatifReadyMail, mail_templates


def generate_justificatif_pdf(purchase_id: int) -> bool:
    """Generate the justificatif PDF for `purchase_id`.

    Returns True on success (or if already generated), False if
    pre-conditions are not met.
    """
    purchase = db.session.get(ArticlePurchase, purchase_id)
    if purchase is None:
        warn(f"justificatif: purchase {purchase_id} not found")
        return False
    if purchase.product_type != PurchaseProduct.JUSTIFICATIF:
        warn(f"justificatif: purchase {purchase_id} is not a JUSTIFICATIF")
        return False
    if purchase.pdf_file is not None:
        return True

    post = db.session.get(Post, purchase.post_id)
    if post is None:
        warn(f"justificatif: post {purchase.post_id} not found")
        return False
    buyer = db.session.get(User, purchase.owner_id)
    if buyer is None or not buyer.email:
        warn(f"justificatif: buyer {purchase.owner_id} missing or has no email")
        return False

    pdf_bytes = _render_pdf(post=post, purchase=purchase, buyer=buyer)
    file_obj = create_file_object(
        content=pdf_bytes,
        original_filename=f"justificatif-{purchase.id}.pdf",
        content_type="application/pdf",
    )
    purchase.pdf_file = file_obj
    db.session.commit()

    signed = purchase.pdf_signed_url(expires_in=3600) or ""
    JustificatifReadyMail(
        sender="contact@aipress24.com",
        recipient=buyer.email,
        sender_mail="contact@aipress24.com",
        article_title=post.title or "(sans titre)",
        pdf_url=signed,
    ).send()
    return True


def _render_pdf(*, post: Post, purchase: ArticlePurchase, buyer: User) -> bytes:
    template_str = rso.read_text(mail_templates, "justificatif.j2")

    excerpt = (post.summary or post.content or "")[:300]
    context = {
        "article_title": post.title or "(sans titre)",
        "author_name": _user_name(post.owner_id),
        "media_name": _publisher_name(post),
        "published_at": post.published_at.format("DD/MM/YYYY HH:mm")
        if post.published_at
        else "",
        "canonical_url": _canonical_url(post),
        "excerpt": excerpt,
        "buyer_name": buyer.full_name,
        "buyer_email": buyer.email,
        "purchase_date": purchase.timestamp.format("DD/MM/YYYY HH:mm")
        if purchase.timestamp
        else "",
        "amount": (purchase.amount_cents or 0) / 100 if purchase.amount_cents else None,
        "currency": purchase.currency,
        "purchase_id": purchase.id,
    }
    html = render_template_string(template_str, **context)
    return HTML(string=html).write_pdf() or b""


def _user_name(user_id: int) -> str:
    user = db.session.get(User, user_id)
    return user.full_name if user else f"user #{user_id}"


def _publisher_name(post: Post) -> str:
    publisher = getattr(post, "publisher", None)
    return publisher.name if publisher else ""


def _canonical_url(post: Post) -> str:
    from flask import current_app, url_for

    try:
        path = url_for("wire.item", id=post.id)
    except Exception:  # noqa: BLE001
        path = f"/wire/{post.id}"
    domain = str(current_app.config.get("SERVER_NAME") or "aipress24.com")
    protocol = "http" if domain.startswith("127.") else "https"
    return f"{protocol}://{domain}{path}"
