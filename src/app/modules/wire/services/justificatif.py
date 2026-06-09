# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Article paywall — justificatif PDF generation (MVP v0).

Synchronous helper invoked by the Dramatiq actor (or directly in
tests). Renders an HTML template, runs WeasyPrint, stores the PDF as
a `FileObject` on the `ArticlePurchase`, and notifies the buyer.

Idempotent: a second call on a purchase that already has `pdf_file`
set is a no-op.

The module is organised as a thin imperative shell
(`generate_justificatif_pdf`, `_render_pdf`) over a pure core
(filename/excerpt/amount/URL/context builders). The pure helpers
are unit-tested directly with stand-in objects ; the shell is
left to b_integration tests that exercise the real DB + WeasyPrint.
"""

from __future__ import annotations

from importlib import resources as rso
from typing import Any

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

# Constants surfaced for the pure helpers + the tests.
_EXCERPT_MAX_LEN = 300
_DATE_FORMAT = "DD/MM/YYYY HH:mm"
_DEFAULT_TITLE = "(sans titre)"
_DEFAULT_DOMAIN = "aipress24.com"


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
    if _is_already_generated(purchase):
        return True

    post = db.session.get(Post, purchase.post_id)
    if post is None:
        warn(f"justificatif: post {purchase.post_id} not found")
        return False
    buyer = db.session.get(User, purchase.owner_id)
    if not _buyer_can_receive(buyer):
        warn(f"justificatif: buyer {purchase.owner_id} missing or has no email")
        return False

    pdf_bytes = _render_pdf(post=post, purchase=purchase, buyer=buyer)
    file_obj = create_file_object(
        content=pdf_bytes,
        original_filename=_build_pdf_filename(purchase.id),
        content_type="application/pdf",
    )
    purchase.pdf_file = file_obj
    db.session.commit()

    signed = purchase.pdf_signed_url(expires_in=3600) or ""
    JustificatifReadyMail(
        sender="contact@aipress24.com",
        recipient=buyer.email,
        sender_mail="contact@aipress24.com",
        article_title=post.title or _DEFAULT_TITLE,
        pdf_url=signed,
    ).send()
    return True


# ---------------------------------------------------------------------------
# Predicates (pure-ish — read attributes, no I/O).
# ---------------------------------------------------------------------------


def _is_already_generated(purchase: Any) -> bool:
    """Pure : true iff the purchase already has a PDF attached.

    Used for idempotency : a second call is a no-op.
    """
    return getattr(purchase, "pdf_file", None) is not None


def _buyer_can_receive(buyer: Any | None) -> bool:
    """Pure : true iff the buyer is loaded AND has an email."""
    if buyer is None:
        return False
    return bool(getattr(buyer, "email", "") or "")


# ---------------------------------------------------------------------------
# Pure string / dict / numeric builders.
# ---------------------------------------------------------------------------


def _build_pdf_filename(purchase_id: int) -> str:
    """Pure : the on-disk PDF filename for a given purchase id."""
    return f"justificatif-{purchase_id}.pdf"


def _build_excerpt(post: Any) -> str:
    """Pure : first 300 chars of summary, falling back to content."""
    return (getattr(post, "summary", "") or getattr(post, "content", "") or "")[
        :_EXCERPT_MAX_LEN
    ]


def _article_title(post: Any) -> str:
    """Pure : article title with the `(sans titre)` fallback."""
    return getattr(post, "title", "") or _DEFAULT_TITLE


def _publisher_name(post: Any) -> str:
    """Pure : `post.publisher.name` with empty-string fallback."""
    publisher = getattr(post, "publisher", None)
    return publisher.name if publisher else ""


def _format_date(value: Any) -> str:
    """Pure : ``arrow``-style ``.format()`` or empty string for falsy."""
    if not value:
        return ""
    return value.format(_DATE_FORMAT)


def _compute_amount(amount_cents: int | None) -> float | None:
    """Pure : cents → euros (float), None / 0 → None.

    Matches the legacy template expectation : the field is omitted
    from the rendering when no amount was captured at checkout.
    """
    if not amount_cents:
        return None
    return amount_cents / 100


def _compose_canonical_url(*, path: str, domain: str) -> str:
    """Pure : protocol + domain + path → full URL.

    Local dev hosts (`127.…`) get plain http ; everything else https.
    """
    protocol = "http" if domain.startswith("127.") else "https"
    return f"{protocol}://{domain}{path}"


def _build_render_context(
    *,
    post: Any,
    purchase: Any,
    buyer: Any,
    author_name: str,
    canonical_url: str,
) -> dict[str, Any]:
    """Pure : assemble the template context dict.

    Author name + canonical URL are passed in because they need
    I/O (DB lookup, Flask routing) to compute.
    """
    return {
        "article_title": _article_title(post),
        "author_name": author_name,
        "media_name": _publisher_name(post),
        "published_at": _format_date(getattr(post, "published_at", None)),
        "canonical_url": canonical_url,
        "excerpt": _build_excerpt(post),
        "buyer_name": getattr(buyer, "full_name", ""),
        "buyer_email": getattr(buyer, "email", ""),
        "purchase_date": _format_date(getattr(purchase, "timestamp", None)),
        "amount": _compute_amount(getattr(purchase, "amount_cents", None)),
        "currency": getattr(purchase, "currency", None),
        "purchase_id": getattr(purchase, "id", None),
    }


# ---------------------------------------------------------------------------
# Imperative shell — kept thin so b_integration covers it.
# ---------------------------------------------------------------------------


def _render_pdf(*, post: Post, purchase: ArticlePurchase, buyer: User) -> bytes:
    template_str = rso.read_text(mail_templates, "justificatif.j2")
    context = _build_render_context(
        post=post,
        purchase=purchase,
        buyer=buyer,
        author_name=_user_name(post.owner_id),
        canonical_url=_canonical_url(post),
    )
    html = render_template_string(template_str, **context)
    return HTML(string=html).write_pdf() or b""


def _user_name(user_id: int) -> str:
    user = db.session.get(User, user_id)
    return user.full_name if user else f"user #{user_id}"


def _canonical_url(post: Post) -> str:
    from flask import current_app, url_for

    try:
        path = url_for("wire.item", id=post.id)
    except Exception:
        path = f"/wire/{post.id}"
    domain = str(current_app.config.get("SERVER_NAME") or _DEFAULT_DOMAIN)
    return _compose_canonical_url(path=path, domain=domain)
