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

No view here tests `user.is_anonymous`: the blueprint's
`before_request` (`app/modules/wire/__init__.py`) raises `Unauthorized`
before any `/wire/*` view is reached. Four guards repeated it, each
commented as indispensable — "without this an anonymous visitor would
see the Stripe price" — and all unreachable (audit 2026-09-02). `g.user`
is therefore a signed-in member throughout this module.
"""

from __future__ import annotations

import unicodedata
from typing import cast

import sqlalchemy as sa
import stripe
from flask import current_app, flash, g, redirect, render_template, request, url_for
from stripe import StripeError
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
from app.modules.wire.services.recipients import parse_recipient_emails
from app.services.stripe.prices import stripe_price_amount
from app.services.stripe.product_mirror import MirroredProduct, active_products
from app.services.stripe.utils import load_stripe_api_key
from app.settings.constants import ARTICLE_CONSULTATION_DURATION

# Upper bound on the recipient list of one CdAO (Consultation d'article
# offerte) purchase. Generous enough for a small team / classroom, low
# enough to block trivial DoS via a 10k-entry POST that would otherwise
# blow through the giftable-check loop and Postgres parameter limits.
MAX_GIFT_BENEFICIARIES = 50

# Taxonomy filters used to pick the right Stripe product for each
# one-off purchase type. See "notes/specs/taxo_produits.md".
#
# Spelled out per product rather than factored into
# `{domain} + {family, offer}`: this table is a **contract**, pinned
# value by value by `test_purchase_view_extras.py` and compared against
# `cli/stripe.py`'s copy by a drift guard. A flat table is what you
# check against the Stripe dashboard.
_PRODUCT_TAXONOMY_FILTERS: dict[PurchaseProduct, dict[str, str]] = {
    PurchaseProduct.JUSTIFICATIF: {
        "domain": "certificate",
        "family": "article",
        "offer": "paid",
    },
    PurchaseProduct.CONSULTATION: {
        "domain": "consultation",
        "family": "article",
        "offer": "paid",
    },
    # Ticket #0194 — gift consultations reuse the same
    # paid consultation Stripe product.
    # Fixme: Does the free consultation product still exist ?
    # The Stripe Checkout line item carries
    # quantity = number of recipients.
    PurchaseProduct.CONSULTATION_GIFT: {
        "domain": "consultation",
        "family": "article",
        "offer": "paid",
    },
    PurchaseProduct.CESSION: {
        "domain": "license",
        "family": "article",
        "offer": "paid",
    },
}

# French genre labels (from the `news-genres` ontology) to taxonomy
# genre values. Identical for every product...
_FRENCH_TO_TAXO_GENRE = {
    "actualite": "news",
    "enquete": "survey",
    "exclusivite": "exclu",
    "interview": "itw",
    "reportage": "report",
}

# ...except "Dossier", the one label whose taxonomy value depends on the
# product: `feature` for the licence and certificate products, `dossier`
# for the consultation ones. Four near-identical maps used to say this
# by repeating the five stable pairs four times over.
_DOSSIER_IS_FEATURE = {PurchaseProduct.JUSTIFICATIF, PurchaseProduct.CESSION}

# TVA rates for modal preview
VAT_RATES_BY_PRODUCT: dict[PurchaseProduct, float] = {
    PurchaseProduct.JUSTIFICATIF: 0.20,
    PurchaseProduct.CONSULTATION: 0.10,
    PurchaseProduct.CONSULTATION_GIFT: 0.10,
    PurchaseProduct.CESSION: 0.10,
}

_TAXO_GENRE_VALUES = {
    "news",
    "feature",
    "survey",
    "exclu",
    "itw",
    "report",
    "dossier",
}


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

    amount_ht_eur = _amount_ht_eur_for(product_type, post)

    vat_rate = VAT_RATES_BY_PRODUCT.get(product_type, 0.20)
    vat_eur, ttc_eur = _compute_vat_ttc(amount_ht_eur, vat_rate)

    return render_template(
        "pages/purchase/buy_modal.j2",
        post=post,
        product_type=product_type,
        amount_ht_eur=amount_ht_eur,
        vat_eur=vat_eur,
        ttc_eur=ttc_eur,
        vat_rate=vat_rate,
        user_cumul_eur=get_user_purchase_total(user.id) / 100,
        org_cumul_eur=get_org_purchase_total(user.organisation_id) / 100,
        stripe_live=bool(current_app.config.get("STRIPE_LIVE_ENABLED")),
        article_consultation_duration=ARTICLE_CONSULTATION_DURATION,
    )


@blueprint.route("/<post_id>/buy/<product>", methods=["POST"])
def buy(post_id: str, product: str):
    """Create a Stripe Checkout session for a one-off article purchase.

    Auth required : the buyer must be logged in (for invoice/email).
    """
    user = cast(User, g.user)

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

    price_id = _price_id_for(product_type, genre=post.genre)
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
    except StripeError as e:
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

    try:
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
            # Ticket #0214: pin card so Stripe doesn't auto-present Link,
            # whose SMS confirmation we can't deliver (no SMS backend).
            payment_method_types=["card"],
        )
    except StripeError as exc:
        warn(f"buy: Stripe Checkout creation failed: {exc}")
        db.session.delete(purchase)
        db.session.commit()
        flash(
            "La passerelle de paiement est momentanément indisponible. "
            "Merci de réessayer dans un instant.",
            "error",
        )
        return redirect(_back_to_post(post))
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

    post = get_obj(post_id, Post)

    amount_ht_eur = _amount_ht_eur_for(PurchaseProduct.CONSULTATION_GIFT, post)

    vat_rate = VAT_RATES_BY_PRODUCT.get(PurchaseProduct.CONSULTATION_GIFT, 0.10)
    vat_eur, ttc_eur = _compute_vat_ttc(amount_ht_eur, vat_rate)

    return render_template(
        "pages/purchase/buy_modal_gift.j2",
        post=post,
        amount_ht_eur=amount_ht_eur,
        vat_eur=vat_eur,
        ttc_eur=ttc_eur,
        vat_rate=vat_rate,
        user_cumul_eur=get_user_purchase_total(user.id) / 100,
        org_cumul_eur=get_org_purchase_total(user.organisation_id) / 100,
        stripe_live=bool(current_app.config.get("STRIPE_LIVE_ENABLED")),
        article_consultation_duration=ARTICLE_CONSULTATION_DURATION,
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

    # The same parser as article sharing: the one here did not split
    # on spaces and validated nothing, so a line of space-separated
    # addresses became a single invalid string — silently, on a billed
    # path.
    emails = parse_recipient_emails(
        "\n".join(request.form.getlist("beneficiary_email"))
    )
    if emails:
        # Case-insensitive email match — Postgres `IN` is case-sensitive
        # so emails stored with mixed case would silently miss otherwise.
        rows = db.session.execute(
            sa.select(User.id).where(sa.func.lower(User.email).in_(emails))
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
        existing_rows = db.session.execute(
            sa.select(User.id).where(User.id.in_(candidate_ids))
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
        genre=post.genre,
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
            # Ticket #0214: pin card (no Link / SMS dead-end).
            payment_method_types=["card"],
        )
    except StripeError as exc:
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


def _amount_ht_eur_for(product: PurchaseProduct, post: Post) -> float | None:
    """The pre-tax price to display for this product on this article.

    `_price_id_for` queries the Stripe catalogue: it stays behind the
    flag, as before. Only the **amount lookup** changed source — the
    local mirror instead of one `Price.retrieve` per render.
    """
    if not current_app.config.get("STRIPE_LIVE_ENABLED"):
        return None
    return _amount_ht_eur(_price_id_for(product, genre=post.genre))


def _amount_ht_eur(price_id: str | None) -> float | None:
    """The displayed pre-tax price, in euros, read from the local mirror.

    Never `stripe.Price.retrieve`: `notes/lessons-learned.md` makes it a
    rule — "any cache window between Stripe's authoritative price and
    the displayed one is a risk that the user pays an amount other than
    the one shown". The `stripe_price` mirror is fed by the
    `price.created/updated/deleted` webhooks, and `flask stripe
    sync-prices` catches it up.

    Which prices may be displayed is `stripe_price_amount`'s rule, not
    a second copy of it here: the paywall button reads the same mirror
    through `stripe_price_display`, and the two must not be able to
    disagree on whether a given price counts.

    `None` when the price is unknown or inactive: the templates then
    show "price unavailable" rather than a wrong amount.
    """
    cents = stripe_price_amount(price_id)
    return None if cents is None else cents / 100


def _normalize_string(value: str) -> str:
    """Lower-case and remove accents from a string."""
    value = value.lower().strip()
    return "".join(
        c for c in unicodedata.normalize("NFKD", value) if not unicodedata.combining(c)
    )


def _post_genre_to_taxo(product: PurchaseProduct, genre: str) -> str | None:
    """Convert a post genre (French ontology label) to a taxonomy genre.

    Returns `None` when the input is empty.
    """
    genre = genre.strip()
    if not genre:
        return None
    if genre in _TAXO_GENRE_VALUES:
        return genre
    normalized = _normalize_string(genre)
    if normalized == "dossier":
        return "feature" if product in _DOSSIER_IS_FEATURE else "dossier"
    return _FRENCH_TO_TAXO_GENRE.get(normalized)


def _is_product_matching_taxonomy(
    prod: MirroredProduct, product: PurchaseProduct, taxo_genre: str | None
) -> bool:
    """Check whether a product matches the new taxonomy filters + genre."""
    filters = _PRODUCT_TAXONOMY_FILTERS.get(product)
    if not filters:
        return False
    metadata = prod.metadata
    for key, value in filters.items():
        if metadata.get(key) != value:
            return False
    return not (taxo_genre is not None and metadata.get("genre") != taxo_genre)


def _select_price_id(
    products: list[MirroredProduct],
    product: PurchaseProduct,
    genre: str = "",
) -> str:
    """Pure : given the mirrored products, return the right price id.

    Reads `prod.default_price` directly rather than going through
    `resolve_product_price`. That helper exists to cope with the shapes
    the Stripe SDK returns, and it reaches for `Price.retrieve` /
    `Price.list` when the price is not already expanded — a network
    call, on the render path, for an object this function discards. The
    mirror has already resolved the id (`stripe_product.default_price_id`,
    else an active row in `stripe_price`), so there is nothing to fetch.

    Returns "" when no candidate matches OR no candidate has a price.
    """
    taxo_genre = _post_genre_to_taxo(product, genre)

    # A product carrying this genre wins; failing that, any product in
    # the same taxonomy family does.
    genre_match = (
        _first_price_id(products, product, taxo_genre) if taxo_genre is not None else ""
    )
    return genre_match or _first_price_id(products, product, None)


def _first_price_id(
    products: list[MirroredProduct],
    product: PurchaseProduct,
    taxo_genre: str | None,
) -> str:
    """The price of the first matching product that has one, else "".

    A product matching the taxonomy but carrying no price is skipped
    rather than returned empty: the catalogue may hold a half-configured
    entry, and the next candidate can still serve the purchase.
    """
    for prod in products:
        if not _is_product_matching_taxonomy(prod, product, taxo_genre):
            continue
        if prod.default_price:
            return prod.default_price
    return ""


def _price_id_for(product: PurchaseProduct, genre: str = "") -> str:
    """Resolve the Stripe price id for a given (product × genre).

    Strategy :
    1. Look for a product matching the new taxonomy
       (`domain`/`family`/`offer`) plus `metadata.genre` when the post
       genre can be mapped to a taxonomy genre.
    2. Fall back to any product in the same taxonomy family.

    Returns "" when neither strategy finds a candidate (handled by
    the caller with a flash).

    Reads the local product mirror, never Stripe. This runs on the
    article render path for every reader who hasn't bought, and listing
    the Stripe catalogue there is what `notes/lessons-learned.md` rules
    out. The mirror is kept current by the `product.*` webhooks and
    repaired hourly by `app.actors.stripe_mirrors`.
    """
    return _select_price_id(active_products(), product, genre)


def _get_purchase_or_404(purchase_id: int) -> ArticlePurchase:
    purchase = db.session.get(ArticlePurchase, purchase_id)
    if purchase is None:
        raise NotFound
    user = cast(User, g.user)
    # `and not user.is_anonymous` exempted anonymous callers from the
    # ownership check instead of refusing them — an IDOR on sequential
    # integer ids, kept out of reach only by the blueprint's
    # `before_request`. The condition now says what it means, and no
    # longer depends on it.
    if purchase.owner_id != user.id:
        raise Forbidden
    return purchase


def _back_to_post(post: Post) -> str:
    if post is None:
        return url_for("wire.wire")
    return url_for("wire.item", id=base62.encode(post.id))


# ---------------------------------------------------------------------------
# Pure helpers (extracted for unit testing — no Flask / DB / Stripe SDK)
# ---------------------------------------------------------------------------

# French standard VAT rate. Stripe `automatic_tax` computes the *real*
# VAT at payment time ; this constant is only used to show a TTC
# estimate in the buy-modal templates.
_FRENCH_VAT_RATE = 0.20


def _cents_to_eur(amount_cents: int | None) -> float | None:
    """Stripe quotes prices in the smallest currency unit (cents for
    EUR). The modal shows euros. `None` round-trips so the template
    can decide what « unknown price » means visually."""
    if amount_cents is None:
        return None
    return amount_cents / 100


def _compute_vat_ttc(
    amount_ht_eur: float | None,
    rate: float = _FRENCH_VAT_RATE,
) -> tuple[float | None, float | None]:
    """Return `(vat_eur, ttc_eur)` for a given HT amount.

    `None` HT round-trips as `(None, None)` so the modal can render
    « prix indisponible » when Stripe is offline.
    """
    if amount_ht_eur is None:
        return None, None
    vat = amount_ht_eur * rate
    return vat, amount_ht_eur + vat


def _parse_beneficiary_ids(raw_ids: list[str]) -> list[int]:
    """Parse a list of raw form values into deduplicated positive ints.

    Rejects non-numeric values, non-positive ids, and duplicates while
    preserving the first-seen order — the request handler then layers
    additional gates (self-gift, existence in `aut_user`, eligibility)
    on top of this list.
    """
    out: list[int] = []
    seen: set[int] = set()
    for raw in raw_ids:
        try:
            uid = int(raw)
        except (TypeError, ValueError):
            continue
        if uid <= 0 or uid in seen:
            continue
        seen.add(uid)
        out.append(uid)
    return out


def _parse_beneficiary_emails(raw_emails: list[str]) -> set[str]:
    """Split a list of textarea values into a lower-cased email set.

    The modal textarea lets the buyer paste emails one-per-line OR
    comma-separated, and the form field can repeat (one « blob » per
    textarea). Empty chunks are dropped. Case is normalised so the
    later `func.lower(email) IN (...)` match is symmetrical.
    """
    blob = "\n".join(raw_emails)
    return {
        chunk.strip().lower()
        for chunk in blob.replace(",", "\n").splitlines()
        if chunk.strip()
    }


def _filter_self_gift(candidate_ids: list[int], buyer_id: int) -> list[int]:
    """Drop the buyer's own user id from a candidate list.

    `is_consultation_giftable_to` doesn't know who the buyer is, so
    without this gate the buyer could pay full price to « gift »
    themselves.
    """
    return [uid for uid in candidate_ids if uid != buyer_id]


def _exceeds_gift_cap(
    candidate_ids: list[int],
    *,
    cap: int = MAX_GIFT_BENEFICIARIES,
) -> bool:
    """True iff the candidate list breaches the recipient cap."""
    return len(candidate_ids) > cap


def _build_checkout_metadata(
    *,
    purchase_id: int,
    post_id: int,
    product: PurchaseProduct,
    beneficiary_count: int | None = None,
) -> dict[str, str]:
    """Pure : assemble the Stripe Checkout `metadata` dict.

    All values are stringified because Stripe metadata is a
    str-to-str map. `beneficiary_count` is only set on the gift
    flow ; passing `None` omits the key entirely.
    """
    meta: dict[str, str] = {
        "purchase_id": str(purchase_id),
        "post_id": str(post_id),
        "product_type": product.value,
    }
    if beneficiary_count is not None:
        meta["beneficiary_count"] = str(beneficiary_count)
    return meta
