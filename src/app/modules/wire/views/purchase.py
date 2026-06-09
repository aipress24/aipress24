# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""One-off article purchases via Stripe Checkout (mode=payment).

Wires the three buy buttons on the article page
(`pages/article/aside.j2`) — Droit de consultation, Justificatif de
publication, Droits de reproduction — to real Stripe Checkout sessions.

This MVP only persists the transaction. The "effect" of each purchase
(access unlock, PDF generation, licence creation) is left to downstream
specs.
"""

from __future__ import annotations

from typing import cast

import stripe
import stripe.error
from flask import current_app, flash, g, redirect, render_template, request, url_for
from werkzeug.exceptions import Forbidden, NotFound

from app.flask.extensions import db
from app.flask.sqla import get_obj
from app.lib.base62 import base62
from app.logging import warn
from app.models.auth import User
from app.modules.wire import blueprint
from app.modules.wire.models import (
    ArticlePurchase,
    ArticlePurchaseGift,
    Post,
    PurchaseProduct,
    PurchaseStatus,
)
from app.services.stripe._client import StripeClient
from app.services.stripe.product import fetch_stripe_product_list
from app.services.stripe.utils import load_stripe_api_key

# Stripe Price ID per one-off product kind. Lives in env / Dynaconf:
#   STRIPE_PRICE_CONSULTATION=price_...
#   STRIPE_PRICE_JUSTIFICATIF=price_... - This is now handled dynamically.
#   STRIPE_PRICE_CESSION=price_...
_PRODUCT_TO_ENV: dict[PurchaseProduct, str] = {}

# Upper bound on the recipient list of one CdAO (Consultation d'article
# offerte) purchase. Generous enough for a small team / classroom, low
# enough to block trivial DoS via a 10k-entry POST that would otherwise
# blow through the giftable-check loop and Postgres parameter limits.
MAX_GIFT_BENEFICIARIES = 50


@blueprint.route("/buy_modal/close", methods=["GET"])
def buy_modal_close() -> str:
    """Empty HTMX response — swapped into `#purchase-modal` to dismiss
    the confirmation modal on Annuler or backdrop click."""
    return ""


@blueprint.route("/<post_id>/buy_modal/<product>", methods=["GET"])
def buy_modal(post_id: str, product: str):
    """HTMX-rendered confirmation modal before Stripe checkout.

    Ticket #0193 — Erick : every buy click should first show the price
    HT / TVA / TTC, the cumul individuel + organisationnel, with three
    buttons (Accepter / Annuler / Retour à la plateforme). Today the
    forms in `pages/article/aside.j2` post directly to `buy`; this
    endpoint sits between, swapping the modal into the page.

    Pricing : we read the unit HT from Stripe when live, then add a
    20% French VAT estimate so the user has a concrete TTC to look at.
    The *real* VAT is computed by Stripe Checkout's `automatic_tax` at
    payment time, so the displayed TTC is an estimate — flagged as
    such in the template.
    """
    from app.modules.wire.services.purchase_aggregates import (
        get_org_purchase_total,
        get_user_purchase_total,
    )

    user = cast(User, g.user)
    # Gate the modal endpoint the same way `buy` gates the POST. Without
    # this, an anonymous visitor can see the Stripe price and the
    # would-be cumul rendered as if they were a buyer ; CESSION price
    # in particular is sensitive (it's the rights tier).
    if user.is_anonymous:
        flash("Connectez-vous pour acheter cet article.", "error")
        return redirect(url_for("security.login"))

    try:
        product_type = PurchaseProduct(product)
    except ValueError as err:
        raise NotFound from err

    post = get_obj(post_id, Post)

    # Same eligibility gate as in `buy` so the modal cannot leak the
    # CESSION price to a user who can't actually buy.
    if product_type == PurchaseProduct.CESSION:
        from app.modules.bw.bw_activation.rights_policy import (
            is_eligible_for_cession,
        )

        if not is_eligible_for_cession(user, post):
            flash(
                "Les droits de reproduction ne sont accessibles "
                "qu'aux abonnés Business Wall.",
                "error",
            )
            return redirect(_back_to_post(post))

    amount_ht_eur: float | None = None
    if current_app.config.get("STRIPE_LIVE_ENABLED") and load_stripe_api_key():
        price_id = _price_id_for(product_type, genre=getattr(post, "genre", "") or "")
        if price_id:
            try:
                price = stripe.Price.retrieve(price_id)
                if price.unit_amount is not None:
                    amount_ht_eur = price.unit_amount / 100
            except stripe.error.StripeError as exc:
                warn(f"buy_modal: failed to retrieve price {price_id}: {exc}")

    vat_eur: float | None = None
    ttc_eur: float | None = None
    if amount_ht_eur is not None:
        vat_eur = amount_ht_eur * 0.20
        ttc_eur = amount_ht_eur + vat_eur

    return render_template(
        "pages/purchase/buy_modal.j2",
        post=post,
        product_type=product_type,
        amount_ht_eur=amount_ht_eur,
        vat_eur=vat_eur,
        ttc_eur=ttc_eur,
        user_cumul_eur=get_user_purchase_total(user.id) / 100,
        org_cumul_eur=get_org_purchase_total(getattr(user, "organisation_id", None))
        / 100,
        stripe_live=bool(current_app.config.get("STRIPE_LIVE_ENABLED")),
    )


@blueprint.route("/<post_id>/buy/<product>", methods=["POST"])
def buy(post_id: str, product: str):
    """Create a Stripe Checkout session for a one-off article purchase.

    Auth required : the buyer must be logged in (for invoice/email).
    """
    user = cast(User, g.user)
    if user.is_anonymous:
        flash("Vous devez être connecté pour effectuer un achat.", "error")
        return redirect(url_for("security.login"))

    try:
        product_type = PurchaseProduct(product)
    except ValueError as err:
        raise NotFound from err

    post = get_obj(post_id, Post)
    if not current_app.config.get("STRIPE_LIVE_ENABLED"):
        flash("Les achats en ligne ne sont pas encore activés.", "error")
        return redirect(_back_to_post(post))

    if product_type == PurchaseProduct.CESSION:
        from app.modules.bw.bw_activation.rights_policy import (
            is_eligible_for_cession,
        )

        if not is_eligible_for_cession(user, post):
            flash(
                "Vous n'êtes pas autorisé à acquérir les droits de "
                "reproduction de cet article.",
                "error",
            )
            return redirect(_back_to_post(post))

    price_id = _price_id_for(product_type, genre=getattr(post, "genre", "") or "")
    if not price_id:
        warn(f"No Stripe price configured for product {product_type.value}")
        flash("Produit momentanément indisponible.", "error")
        return redirect(_back_to_post(post))

    if not load_stripe_api_key():
        flash("Configuration Stripe manquante.", "error")
        return redirect(_back_to_post(post))

    try:
        price = stripe.Price.retrieve(price_id)
        mode = "subscription" if price.recurring else "payment"
    except stripe.error.StripeError as e:
        warn(f"Failed to retrieve Stripe price {price_id}: {e}")
        flash("Produit momentanément indisponible (erreur Stripe).", "error")
        return redirect(_back_to_post(post))

    purchase = ArticlePurchase(
        post_id=post.id,
        owner_id=user.id,
        product_type=product_type,
        status=PurchaseStatus.PENDING,
    )
    db.session.add(purchase)
    db.session.commit()

    success_url = url_for(
        "wire.purchase_success",
        purchase_id=purchase.id,
        _external=True,
    )
    cancel_url = url_for(
        "wire.purchase_cancel",
        purchase_id=purchase.id,
        _external=True,
    )

    checkout = stripe.checkout.Session.create(
        mode=mode,
        customer_email=user.email,
        line_items=[{"price": price_id, "quantity": 1}],
        success_url=success_url,
        cancel_url=cancel_url,
        metadata={
            "purchase_id": str(purchase.id),
            "post_id": str(post.id),
            "product_type": product_type.value,
        },
        automatic_tax={"enabled": True},
    )
    return redirect(checkout.url, code=303)


@blueprint.route("/<post_id>/buy_modal_gift", methods=["GET"])
def buy_modal_gift(post_id: str):
    """Ticket #0194 — confirmation modal for the « Consultation
    d'article offerte » action. Renders a textarea where the buyer
    pastes recipient emails (one per line or comma-separated), the
    per-recipient HT/TVA/TTC, and the cumul individuel + organisationnel.

    The « Accepter » button POSTs to `/wire/<id>/buy_gift` with the
    emails ; the route handler resolves them to user ids server-side.
    """
    from app.modules.wire.services.purchase_aggregates import (
        get_org_purchase_total,
        get_user_purchase_total,
    )

    user = cast(User, g.user)
    # Mirror the `buy` anonymous guard so the modal cannot leak prices
    # or cumul to an unauthenticated visitor.
    if user.is_anonymous:
        flash("Connectez-vous pour offrir cet article.", "error")
        return redirect(url_for("security.login"))

    post = get_obj(post_id, Post)

    amount_ht_eur: float | None = None
    if current_app.config.get("STRIPE_LIVE_ENABLED") and load_stripe_api_key():
        price_id = _price_id_for(
            PurchaseProduct.CONSULTATION_GIFT,
            genre=getattr(post, "genre", "") or "",
        )
        if price_id:
            try:
                price = stripe.Price.retrieve(price_id)
                if price.unit_amount is not None:
                    amount_ht_eur = price.unit_amount / 100
            except stripe.error.StripeError as exc:
                warn(f"buy_modal_gift: failed to retrieve price: {exc}")

    vat_eur: float | None = None
    ttc_eur: float | None = None
    if amount_ht_eur is not None:
        vat_eur = amount_ht_eur * 0.20
        ttc_eur = amount_ht_eur + vat_eur

    return render_template(
        "pages/purchase/buy_modal_gift.j2",
        post=post,
        amount_ht_eur=amount_ht_eur,
        vat_eur=vat_eur,
        ttc_eur=ttc_eur,
        user_cumul_eur=get_user_purchase_total(user.id) / 100,
        org_cumul_eur=get_org_purchase_total(getattr(user, "organisation_id", None))
        / 100,
        stripe_live=bool(current_app.config.get("STRIPE_LIVE_ENABLED")),
    )


@blueprint.route("/<post_id>/buy_gift", methods=["POST"])
def buy_gift(post_id: str):
    """Ticket #0194 — buy a CONSULTATION_GIFT for N beneficiaries.

    Form data : `beneficiary_user_id` (multiple values, integer user
    ids of the AiPRESS24 members the buyer wants to gift). Each
    beneficiary is validated via `is_consultation_giftable_to` — ones
    that already have access are filtered out (no double-billing).
    Stripe Checkout is then opened with `quantity=N` on the same
    consultation price.
    """
    from app.modules.wire.services.purchase_aggregates import (
        is_consultation_giftable_to,
    )

    user = cast(User, g.user)
    if user.is_anonymous:
        flash("Vous devez être connecté pour offrir un article.", "error")
        return redirect(url_for("security.login"))

    post = get_obj(post_id, Post)
    if not current_app.config.get("STRIPE_LIVE_ENABLED"):
        flash("Les achats en ligne ne sont pas encore activés.", "error")
        return redirect(_back_to_post(post))

    # Two input shapes :
    # - `beneficiary_user_id` (one or more) — machine form, used by
    #   front-end JS that has already resolved AiPRESS24 members.
    # - `beneficiary_email` (newline- or comma-separated, can repeat) —
    #   user form (textarea on the modal). Resolved here to user ids ;
    #   emails that don't match an `aut_user.email` row are dropped.
    raw_ids = request.form.getlist("beneficiary_user_id")
    candidate_ids: list[int] = []
    seen: set[int] = set()
    for raw in raw_ids:
        try:
            uid = int(raw)
        except (TypeError, ValueError):
            continue
        if uid <= 0 or uid in seen:
            continue
        seen.add(uid)
        candidate_ids.append(uid)

    raw_emails_blob = "\n".join(request.form.getlist("beneficiary_email"))
    emails = {
        e.strip().lower()
        for chunk in raw_emails_blob.replace(",", "\n").splitlines()
        for e in [chunk]
        if e.strip()
    }
    if emails:
        from sqlalchemy import func as sa_func, select as sa_select

        from app.models.auth import User as _User

        # Case-insensitive email match — Postgres `IN` is case-sensitive
        # so emails stored with mixed case would silently miss otherwise.
        rows = db.session.execute(
            sa_select(_User.id).where(sa_func.lower(_User.email).in_(emails))
        ).all()
        for (uid,) in rows:
            if uid and uid not in seen:
                seen.add(uid)
                candidate_ids.append(uid)

    # Cap the recipient count. The form is client-side ; without this
    # an authenticated user can post thousands of ids and DoS a worker
    # on the giftable-check loop below.
    if len(candidate_ids) > MAX_GIFT_BENEFICIARIES:
        flash(
            f"Vous ne pouvez offrir un article qu'à {MAX_GIFT_BENEFICIARIES} "
            "destinataires en une seule fois.",
            "error",
        )
        return redirect(_back_to_post(post))

    # Drop self-gifts : `is_consultation_giftable_to` doesn't know who
    # the buyer is, so it would otherwise let a buyer pay full price to
    # « gift » themselves.
    candidate_ids = [uid for uid in candidate_ids if uid != user.id]

    # Validate that each candidate id corresponds to a real `aut_user`
    # row. Without this, phantom ids would pass
    # `is_consultation_giftable_to` (which only checks for existing PAID
    # rows) and become orphan `ArticlePurchaseGift` rows — buyer billed
    # for ghost seats.
    if candidate_ids:
        from sqlalchemy import select as sa_select

        from app.models.auth import User as _User

        existing_rows = db.session.execute(
            sa_select(_User.id).where(_User.id.in_(candidate_ids))
        ).all()
        existing_ids = {uid for (uid,) in existing_rows}
        candidate_ids = [uid for uid in candidate_ids if uid in existing_ids]

    # Filter out recipients who already have access.
    eligible_ids = [
        uid for uid in candidate_ids if is_consultation_giftable_to(uid, post.id)
    ]
    if not eligible_ids:
        flash(
            "Aucun destinataire éligible : ils possèdent déjà un accès à cet article.",
            "error",
        )
        return redirect(_back_to_post(post))

    quantity = len(eligible_ids)

    price_id = _price_id_for(
        PurchaseProduct.CONSULTATION_GIFT,
        genre=getattr(post, "genre", "") or "",
    )
    if not price_id:
        warn("No Stripe price configured for CONSULTATION_GIFT")
        flash("Produit momentanément indisponible.", "error")
        return redirect(_back_to_post(post))

    if not load_stripe_api_key():
        flash("Configuration Stripe manquante.", "error")
        return redirect(_back_to_post(post))

    purchase = ArticlePurchase(
        post_id=post.id,
        owner_id=user.id,
        product_type=PurchaseProduct.CONSULTATION_GIFT,
        status=PurchaseStatus.PENDING,
    )
    db.session.add(purchase)
    db.session.flush()
    for uid in eligible_ids:
        db.session.add(
            ArticlePurchaseGift(
                purchase_id=purchase.id,
                beneficiary_user_id=uid,
            )
        )
    db.session.commit()

    success_url = url_for(
        "wire.purchase_success",
        purchase_id=purchase.id,
        _external=True,
    )
    cancel_url = url_for(
        "wire.purchase_cancel",
        purchase_id=purchase.id,
        _external=True,
    )

    # Guard the Stripe call. Without try/except, any Stripe-side error
    # (network blip, 5xx, rate limit) leaves the PENDING purchase + N
    # gift rows orphaned with no checkout session the buyer can resume
    # from. On error we delete the would-be-orphan rows and flash a
    # generic « try again » message.
    try:
        checkout = stripe.checkout.Session.create(
            mode="payment",
            customer_email=user.email,
            line_items=[{"price": price_id, "quantity": quantity}],
            success_url=success_url,
            cancel_url=cancel_url,
            metadata={
                "purchase_id": str(purchase.id),
                "post_id": str(post.id),
                "product_type": PurchaseProduct.CONSULTATION_GIFT.value,
                "beneficiary_count": str(quantity),
            },
            automatic_tax={"enabled": True},
        )
    except stripe.error.StripeError as exc:
        warn(f"buy_gift: Stripe Checkout creation failed: {exc}")
        db.session.query(ArticlePurchaseGift).filter_by(
            purchase_id=purchase.id
        ).delete()
        db.session.delete(purchase)
        db.session.commit()
        flash(
            "La passerelle de paiement est momentanément indisponible. "
            "Merci de réessayer dans un instant.",
            "error",
        )
        return redirect(_back_to_post(post))

    return redirect(checkout.url, code=303)


@blueprint.route("/purchase/<int:purchase_id>/success")
def purchase_success(purchase_id: int):
    purchase = _get_purchase_or_404(purchase_id)
    return render_template(
        "pages/purchase/success.j2",
        purchase=purchase,
        back_url=_back_to_post(purchase.post),
    )


@blueprint.route("/purchase/<int:purchase_id>/cancel")
def purchase_cancel(purchase_id: int):
    purchase = _get_purchase_or_404(purchase_id)
    return render_template(
        "pages/purchase/cancel.j2",
        purchase=purchase,
        back_url=_back_to_post(purchase.post),
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


# Marker used to pick the right Stripe product for each one-off
# purchase type. Each product can additionally carry `metadata.genre`
# (ticket #0192 — pricing par genre) ; when a `genre` is passed to
# `_price_id_for`, the helper prefers the matching genre-specific
# product and falls back to the flat lookup so existing single-product
# setups keep working.
_PRODUCT_STRIPE_MARKER: dict[PurchaseProduct, tuple[str, str]] = {
    PurchaseProduct.JUSTIFICATIF: ("product_type", "j-article"),
    PurchaseProduct.CONSULTATION: ("article", "c-article"),
    # Ticket #0194 — gift consultations reuse the same Stripe product
    # as a regular consultation (« Tarif Consultation d'article par
    # destinataire »). The Stripe Checkout line item carries
    # quantity = number of recipients.
    PurchaseProduct.CONSULTATION_GIFT: ("article", "c-article"),
    PurchaseProduct.CESSION: ("article", "cd-article"),
}


def _select_price_id(
    products: list,
    product: PurchaseProduct,
    genre: str = "",
) -> str:
    """Pure : given a list of Stripe products, return the right price id.

    Extracted from `_price_id_for` so the lookup logic can be unit-
    tested without any Stripe SDK or live HTTP call. The shape each
    product must expose is the one the Stripe SDK gives us — attribute
    access to `.metadata` (mapping) and `.default_price` (object with
    `.id`, or falsy).

    Returns "" when no candidate matches.
    """
    marker = _PRODUCT_STRIPE_MARKER.get(product)
    if marker is None:
        return ""
    key, value = marker

    if genre:
        for prod in products:
            if (
                prod.metadata.get(key) == value
                and prod.metadata.get("genre") == genre
                and prod.default_price
            ):
                return prod.default_price.id

    # Back-compat fallback : flat lookup, no genre constraint.
    for prod in products:
        if prod.metadata.get(key) == value and prod.default_price:
            return prod.default_price.id

    return ""


def _price_id_for(
    product: PurchaseProduct,
    genre: str = "",
    *,
    client: StripeClient | None = None,
) -> str:
    """Resolve the Stripe price id for a given (product × genre).

    Strategy :
    1. If `genre` is provided, look for a product matching both the
       product-type marker AND `metadata.genre == genre`.
    2. Otherwise (or if no genre-specific product exists), fall back
       to any product matching the product-type marker — the pre-#0192
       behaviour.

    Returns "" when neither path finds a candidate (handled by the
    caller with a flash).

    Pass an explicit `client` to inject a fake StripeClient — used by
    unit tests to seed canned products without monkeypatching. The
    default production path goes through `fetch_stripe_product_list`'s
    own default client (the real Stripe SDK adapter).
    """
    products = fetch_stripe_product_list(active=True, client=client)
    return _select_price_id(products, product, genre)


def _get_purchase_or_404(purchase_id: int) -> ArticlePurchase:
    purchase = db.session.get(ArticlePurchase, purchase_id)
    if purchase is None:
        raise NotFound
    user = cast(User, g.user)
    if not user.is_anonymous and purchase.owner_id != user.id:
        raise Forbidden
    return purchase


def _back_to_post(post: Post) -> str:
    if post is None:
        return url_for("wire.wire")
    return url_for("wire.item", id=base62.encode(post.id))
