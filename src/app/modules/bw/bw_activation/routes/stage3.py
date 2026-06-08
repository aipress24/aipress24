# Copyright (c) 2025, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Stage 3: Activation routes (free and paid)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, cast

import stripe
from flask import (
    current_app,
    flash,
    g,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from sqlalchemy.orm import scoped_session
from svcs.flask import container

from app.flask.extensions import db
from app.logging import warn
from app.modules.admin.org_email_utils import change_members_emails
from app.modules.bw.bw_activation import bp
from app.modules.bw.bw_activation.bw_creation import (
    create_new_free_bw_record,
    create_new_paid_bw_record,
)
from app.modules.bw.bw_activation.config import BW_TYPES, BWTYPE_ALLOWED_PRODUCTS
from app.modules.bw.bw_activation.models import (
    BusinessWall,
    BWStatus,
    Subscription,
    SubscriptionStatus,
)
from app.modules.bw.bw_activation.user_utils import current_business_wall
from app.modules.bw.bw_activation.utils import (
    ERR_NO_ORGANISATION,
    ERR_NOT_MANAGER,
    ERR_UNKNOWN_ACTION,
    fill_session,
    is_bw_manager_or_admin,
)
from app.services.stripe.product import fetch_bw_product_list
from app.services.stripe.utils import (
    get_stripe_public_key,
    load_stripe_api_key,
    # load_pricing_table_id,
)

if TYPE_CHECKING:
    from stripe import Product

    from app.models.auth import User


# ===== FREE ACTIVATION =====


@bp.route("/activate-free/<bw_type>")
def activate_free_page(bw_type: str):
    """Step 3: Page for free BW activation with CGV acceptance."""
    if bw_type not in BW_TYPES or not BW_TYPES[bw_type]["free"]:
        return redirect(url_for("bw_activation.confirm_subscription"))

    if not session.get("bw_type_confirmed"):
        return redirect(url_for("bw_activation.confirm_subscription"))

    if not session.get("contacts_confirmed"):
        return redirect(url_for("bw_activation.nominate_contacts"))

    bw_info = BW_TYPES[bw_type]
    return render_template(
        "bw_activation/activate_free.html",
        bw_type=bw_type,
        bw_info=bw_info,
    )


@bp.route("/activate_free/<bw_type>", methods=["POST"])
def activate_free(bw_type: str):
    """Process free Business Wall activation."""
    if bw_type not in BW_TYPES or not BW_TYPES[bw_type]["free"]:
        return redirect(url_for("bw_activation.index"))

    cgv_accepted = request.form.get("cgv_accepted") == "on"
    if cgv_accepted:
        session["bw_type"] = bw_type
        session["bw_activated"] = True
        return redirect(url_for("bw_activation.confirmation_free"))

    return redirect(url_for("bw_activation.activate_free_page", bw_type=bw_type))


@bp.route("/confirmation/free")
def confirmation_free():
    """Confirmation page for free BW activation."""
    if not session.get("bw_activated") or not session.get("bw_type"):
        return redirect(url_for("bw_activation.index"))

    bw_type = session["bw_type"]
    bw_info = BW_TYPES.get(bw_type, {})

    # Idempotence guard : Firefox occasionally prefetches the
    # /confirmation/free URL after the activate_free POST redirect,
    # firing this handler twice while session["bw_activated"] is
    # still set. Without this guard, `create_new_free_bw_record`
    # would create two BW rows on a single user-visible navigation.
    #
    # We require the existing BW to be MANAGED by the current user
    # — not merely « exists somewhere ». Without this strictness, a
    # stale `session["bw_id"]` left over from a previous attempt
    # (or from a different org the user briefly belonged to) made
    # this idempotency check « find an existing BW » → bail without
    # creating anything new → user sees « Activation réussie » but
    # nothing was persisted, then « Accès non autorisé » on the
    # next click. Ref: bugs #0110, #0115, #0116, #0117.
    user = cast("User", g.user)
    existing = current_business_wall(user)
    if existing is not None and existing.status != BWStatus.CANCELLED.value:
        if is_bw_manager_or_admin(user, existing):
            # Bug #0071/2 : a DRAFT BW (e.g. pre-Stripe pre-checkout, or
            # left dangling because the webhook never fired) used to be
            # treated as « already activated » and the page rendered
            # the confirmation card without flipping the status. The
            # opportunity gate later rejected it (ACTIVE-only) and the
            # user saw the same banner forever. Finalise the DRAFT
            # here so the user's mental model (« j'ai configuré mon
            # BW ») matches the underlying state.
            if existing.status != BWStatus.ACTIVE.value:
                existing.status = BWStatus.ACTIVE.value  # type: ignore[assignment]
                # Link organisation to BW
                org = existing.get_organisation()
                if org:
                    org.bw_id = existing.id
                    org.bw_active = existing.bw_type
                db.session.commit()
            fill_session(existing)
            return render_template(
                "bw_activation/02_activation_gratuit_confirme.html",
                bw_type=bw_type,
                bw_info=bw_info,
            )
        # Bug #0139: a member of the BW's organisation who is NOT a
        # manager must NOT be silently promoted to BW_OWNER here.
        # `confirmation_free` is a GET whose only guard is
        # `session["bw_activated"]` (set merely by accepting the CGV),
        # so the previous auto-grant let any org member self-escalate
        # to BW_OWNER with no invitation and no acceptance. We still
        # must not create a duplicate BW for them
        # (#0110/#0115/#0116/#0117) — so bail out to "not authorized".
        # A role must be obtained through an explicit invitation +
        # acceptance in the preferences flow, not by walking this URL.
        org = existing.get_organisation()
        if org and user in org.members:
            warn(
                f"confirmation_free: non-manager member {user.email} of "
                f"org with BW {existing.id} — no role granted (#0139)"
            )
            session["error"] = ERR_NOT_MANAGER
            return redirect(url_for("bw_activation.not_authorized"))
    # Stale `session["bw_id"]` would otherwise prevent a fresh
    # creation attempt from succeeding. Drop it so the new BW
    # picked by `current_business_wall(user)` post-creation is the
    # one we just made.
    session.pop("bw_id", None)

    # here create an actual BW instance
    created = create_new_free_bw_record(session)
    if created:
        # Commit the transaction now
        db_session = container.get(scoped_session)
        db_session.commit()

        # ensure  owner of the BW is member of the organisation
        user = cast("User", g.user)
        current_bw = current_business_wall(user)
        if current_bw is not None:
            # Pin the new BW into the session so /BW/dashboard
            # resolves to it directly (instead of falling back to
            # the org's previously-active BW, which may be stale).
            fill_session(current_bw)
            org = current_bw.get_organisation()
            if org:
                change_members_emails(org, f"{user.email}")

        return render_template(
            "bw_activation/02_activation_gratuit_confirme.html",
            bw_type=bw_type,
            bw_info=bw_info,
        )
    return redirect(url_for("bw_activation.index"))


# ===== PAID ACTIVATION =====


@bp.route("/pricing/<bw_type>")
def pricing_page(bw_type: str):
    """Step 3: Page for paid BW pricing information."""
    if bw_type not in BW_TYPES or BW_TYPES[bw_type]["free"]:
        return redirect(url_for("bw_activation.confirm_subscription"))

    if not session.get("bw_type_confirmed"):
        return redirect(url_for("bw_activation.confirm_subscription"))

    if not session.get("contacts_confirmed"):
        return redirect(url_for("bw_activation.nominate_contacts"))

    bw_info = BW_TYPES[bw_type]
    return render_template(
        "bw_activation/pricing.html",
        bw_type=bw_type,
        bw_info=bw_info,
    )


@bp.route("/set_pricing/<bw_type>", methods=["POST"])
def set_pricing(bw_type: str):
    """Set pricing information for paid BW."""
    if bw_type not in BW_TYPES or BW_TYPES[bw_type]["free"]:
        return redirect(url_for("bw_activation.index"))

    # Validate CGV acceptance (required for paid types)
    cgv_accepted = request.form.get("cgv_accepted") == "on"
    if not cgv_accepted:
        # CGV not accepted, redirect back to pricing page
        return redirect(url_for("bw_activation.pricing_page", bw_type=bw_type))

    pricing_field = str(BW_TYPES[bw_type]["pricing_field"])
    try:
        pricing_value = int(request.form.get(pricing_field, "0"))
        if pricing_value > 0:
            session["bw_type"] = bw_type
            session["pricing_value"] = pricing_value
            session["cgv_accepted"] = True  # Store CGV acceptance
            # Ticket #0182 — preserve the count across the
            # activation funnel so stage B01 (`configure_content`)
            # can pre-select the « Taille de l'organisation »
            # dropdown without asking the user to type it again.
            # `pricing_value` is wiped by `fill_session` after BW
            # creation ; this companion key is not.
            if pricing_field == "employee_count":
                session["bw_employee_count"] = pricing_value
            return redirect(url_for("bw_activation.payment", bw_type=bw_type))
    except ValueError:
        pass

    return redirect(url_for("bw_activation.index"))


@bp.route("/payment/<bw_type>")
def payment(bw_type: str):
    """Payment page for paid BW.

    Two modes :
    - **Simulation** (default, flag `STRIPE_LIVE_ENABLED=False`) : form
      cheapskate + POST to `simulate_payment` for dev.
    - **Stripe live** : embeds a `<stripe-pricing-table>` widget pointing
      at the Pricing Table configured for this BW type. The widget
      creates the Checkout Session client-side and the
      `checkout.session.completed` webhook activates the BW.
    """
    if bw_type not in BW_TYPES or BW_TYPES[bw_type]["free"]:
        return redirect(url_for("bw_activation.index"))

    if not session.get("pricing_value"):
        return redirect(url_for("bw_activation.index"))

    bw_info = BW_TYPES[bw_type]
    ctx: dict[str, Any] = {
        "bw_type": bw_type,
        "bw_info": bw_info,
        "pricing_value": session["pricing_value"],
        "stripe_live": False,
    }

    if current_app.config.get("STRIPE_LIVE_ENABLED"):
        return _payment_live_enabled(bw_type, ctx)
    return _payment_simulation(bw_type, ctx)


def _payment_simulation(_bw_type: str, ctx: dict[str, Any]):
    return render_template("bw_activation/payment.html", **ctx)


def _select_product_for_quantity(products: list[Product], quantity: int) -> Product:
    """Select the product whose 'maximum' metadata is >= quantity."""
    if not products:
        msg = "Empty list of products"
        raise ValueError(msg)

    parsed_products = []
    for p in products:
        meta = p.get("metadata", {})
        max_str = meta.get("maximum") or meta.get("Maximum") or meta.get("MAXIMUM")
        try:
            max_val = int(max_str)
        except (ValueError, TypeError):
            max_val = float("inf")
        parsed_products.append((max_val, p))

    parsed_products.sort()

    for max_val, p in parsed_products:
        if quantity <= max_val:
            return p

    # if no threshold found send back the largest product
    return parsed_products[-1][1]


@bp.route("/checkout/<bw_type>", methods=["POST"])
def checkout(bw_type: str):
    """Create a Stripe Checkout Session and redirect to checkout page."""
    if bw_type not in BW_TYPES or BW_TYPES[bw_type]["free"]:
        return redirect(url_for("bw_activation.index"))

    draft_bw = _get_or_create_draft_bw_for_checkout(g.user, bw_type)
    if draft_bw is None:
        # should never fail
        session["error"] = ERR_NO_ORGANISATION
        return redirect(url_for("bw_activation.not_authorized"))

    allowed_products = allowed_bw_product_list(bw_type)
    if not allowed_products:
        return redirect(url_for("bw_activation.index"))

    load_stripe_api_key()

    # For subscription Products, quantity only used for selecting the product
    try:
        quantity = int(session.get("pricing_value", 1))
    except (ValueError, TypeError):
        quantity = 1

    quantity = max(1, quantity)

    # Automatically choose the product based on quantity
    chosen_product = _select_product_for_quantity(allowed_products, quantity)

    # Extract the price ID
    # it might be a dict due to expansion, or just the string ID)
    default_price = chosen_product.get("default_price")
    if isinstance(default_price, dict):
        price_id = default_price.get("id")
    else:
        price_id = default_price

    if not price_id:
        warn(f"No default price found for product {chosen_product.id}")
        session["error"] = ERR_UNKNOWN_ACTION
        return redirect(url_for("bw_activation.not_authorized"))

    # For subscription Products, quantity only used for selecting the product
    items = [{"price": price_id, "quantity": 1}]

    success_url = url_for(
        "bw_activation.payment_success",
        bw_type=bw_type,
        _external=True,
    )
    cancel_url = url_for(
        "bw_activation.payment_cancel",
        bw_type=bw_type,
        _external=True,
    )

    checkout_kwargs: dict[str, Any] = {
        "mode": "subscription",
        "line_items": items,
        "success_url": success_url,
        "cancel_url": cancel_url,
        "client_reference_id": str(draft_bw.id),
        "metadata": {
            "bw_id": str(draft_bw.id),
            "bw_type": bw_type,
            "user_id": str(g.user.id),
        },
        "automatic_tax": {"enabled": True},
    }

    # Keep exsiting customer ID
    org = draft_bw.get_organisation()
    if org and org.stripe_customer_id:
        checkout_kwargs["customer"] = org.stripe_customer_id
    else:
        checkout_kwargs["customer_email"] = g.user.email

    checkout_session = stripe.checkout.Session.create(**checkout_kwargs)
    return redirect(checkout_session.url, code=303)


@bp.route("/payment-success/<bw_type>")
def payment_success(bw_type: str):
    """Landing page after successful Stripe checkout."""
    # Actual activation happens via webhook.
    # We just display a success message.
    return render_template(
        "bw_activation/payment_success.html",
        bw_type=bw_type,
        bw_info=BW_TYPES.get(bw_type),
    )


@bp.route("/payment-cancel/<bw_type>")
def payment_cancel(bw_type: str):
    """Landing page after cancelled Stripe checkout."""
    flash(
        "Le paiement a été annulé. Vous pouvez réessayer quand vous le souhaitez.",
        "info",
    )
    return redirect(url_for("bw_activation.payment_page", bw_type=bw_type))


def allowed_bw_product_list(bw_type: str) -> list[Product]:
    results: list[Product] = []
    allowed_values = set(BWTYPE_ALLOWED_PRODUCTS.get(bw_type, []))
    if not allowed_values:
        return results
    prods = fetch_bw_product_list()
    for prod in prods:
        raw_metadata = prod.get("metadata", {})
        metadata_dict = dict(raw_metadata) if raw_metadata else {}
        metadata_dict = {str(k).lower(): v for k, v in metadata_dict.items()}
        if metadata_dict.get("subs", "") in allowed_values:
            results.append(prod)
    return results


def _payment_live_enabled(bw_type: str, ctx: dict[str, Any]):
    warn("in /payment/<bw_type> live")
    draft_bw = _get_or_create_draft_bw_for_checkout(g.user, bw_type)

    if draft_bw is None:
        session["error"] = ERR_NO_ORGANISATION
        return redirect(url_for("bw_activation.not_authorized"))

    # pricing_table_id = load_pricing_table_id(bw_type)

    allowed_products = allowed_bw_product_list(bw_type)
    if not allowed_products:
        session["error"] = ERR_UNKNOWN_ACTION
        warn(f"Bug: no allowd stripe product found for bw_type {bw_type!r}")
        return redirect(url_for("bw_activation.not_authorized"))

    # For subscription Products, quantity only used for selecting the product
    try:
        quantity = int(session.get("pricing_value", 1))
    except (ValueError, TypeError):
        quantity = 1

    quantity = max(1, quantity)

    # Automatically choose the product based on quantity for display
    chosen_product = _select_product_for_quantity(allowed_products, quantity)

    ctx.update(
        {
            "stripe_live": True,
            "bw_id": str(draft_bw.id),
            "stripe_public_key": get_stripe_public_key(),
            "user_email": g.user.email,
            "chosen_product": chosen_product,
        }
    )
    return render_template("bw_activation/payment.html", **ctx)


@bp.route("/stripe-info/<bw_type>", methods=["GET", "POST"])
def stripe_info(bw_type: str):
    """Collect Stripe billing information for PR BW before checkout.

    When Stripe live mode is enabled. The collected SIRET, email, etc.
    are stored on a draft BusinessWall so the subsequent Pricing Table
    checkout and webhook flow uses them.
    """
    if bw_type not in BW_TYPES or BW_TYPES[bw_type]["free"]:
        return redirect(url_for("bw_activation.index"))

    if not session.get("bw_type_confirmed"):
        return redirect(url_for("bw_activation.confirm_subscription"))

    # if not session.get("contacts_confirmed"):
    #     return redirect(url_for("bw_activation.nominate_contacts"))

    bw_info = BW_TYPES[bw_type]
    user = cast("User", g.user)

    if request.method == "POST":
        cgv_accepted = request.form.get("cgv_accepted") == "on"
        if not cgv_accepted:
            return redirect(url_for("bw_activation.stripe_info", bw_type=bw_type))

        draft_bw = _get_or_create_draft_bw_for_checkout(user, bw_type)
        if draft_bw is not None:
            draft_bw.siren = request.form.get("siren", "").strip()
            draft_bw.payer_email = request.form.get(
                "payer_email", user.email or ""
            ).strip()
            company_name = request.form.get("company_name", "").strip()
            draft_bw.name = company_name
            draft_bw.postal_address = request.form.get("postal_address", "").strip()
            draft_bw.tel_standard = request.form.get("tel_standard", "").strip()
            org = user.organisation
            if org and company_name:
                # sync org.bw_name with new BW.name
                org.bw_name = company_name
            db.session.commit()

        session["bw_type"] = bw_type
        session["pricing_value"] = bw_info.get("pricing_default", 1)
        session["cgv_accepted"] = True
        return redirect(url_for("bw_activation.payment", bw_type=bw_type))

    default_name = ""
    if user.organisation and user.organisation.name:
        default_name = user.organisation.name

    ctx = {
        "bw_type": bw_type,
        "bw_info": bw_info,
        "default_email": user.email or "",
        "default_name": default_name,
    }
    return render_template("bw_activation/stripe_info.html", **ctx)


def _get_or_create_draft_bw_for_checkout(
    user: User, bw_type: str
) -> BusinessWall | None:
    """Return a DRAFT Business Wall for this user/bw_type, creating one
    if none exists yet. Used as the target of the Stripe Pricing Table's
    `client-reference-id`.
    """

    org = getattr(user, "organisation", None)
    if org is None:
        warn("payment: user has no organisation, cannot draft BW for checkout")
        return None

    existing = (
        db.session.query(BusinessWall)
        .filter(BusinessWall.organisation_id == org.id)
        .filter(BusinessWall.bw_type == bw_type)
        .filter(BusinessWall.status == BWStatus.DRAFT.value)
        .first()
    )
    if existing is not None:
        return existing

    bw = BusinessWall(
        bw_type=bw_type,
        status=BWStatus.DRAFT.value,
        is_free=False,
        owner_id=int(user.id),
        payer_id=int(user.id),
        organisation_id=int(org.id),
    )
    db.session.add(bw)
    db.session.flush()
    # Placeholder Subscription row so the webhook can update it cleanly
    sub = Subscription(
        business_wall_id=bw.id,
        status=SubscriptionStatus.PENDING.value,
        pricing_field="stripe",
        pricing_tier="via_pricing_table",
        monthly_price=0,
        annual_price=0,
        cgv_accepted_at=datetime.now(UTC),
    )
    db.session.add(sub)
    db.session.commit()
    return bw


@bp.route("/simulate_payment/<bw_type>", methods=["POST"])
def simulate_payment(bw_type: str):
    """Simulate payment and activate paid BW.

    Dev-only shortcut for the days before real Stripe Checkout was
    wired. Security VULN-002 : MUST be a no-op when `STRIPE_LIVE_ENABLED`
    is on — otherwise any authenticated user can self-grant a paid BW
    by POSTing here after a legitimate `/set_pricing/<bw_type>` POST
    primed `session["pricing_value"]`. In live mode the only
    activation path is the `checkout.session.completed` webhook.
    """
    if current_app.config.get("STRIPE_LIVE_ENABLED"):
        return redirect(url_for("bw_activation.index"))

    if bw_type not in BW_TYPES or BW_TYPES[bw_type]["free"]:
        return redirect(url_for("bw_activation.index"))

    if session.get("pricing_value"):
        session["bw_activated"] = True
        return redirect(url_for("bw_activation.confirmation_paid"))

    return redirect(url_for("bw_activation.index"))


@bp.route("/confirmation/paid")
def confirmation_paid():
    """Confirmation page for paid BW activation."""
    if not session.get("bw_activated") or not session.get("bw_type"):
        return redirect(url_for("bw_activation.index"))

    bw_type = session["bw_type"]
    bw_info = BW_TYPES.get(bw_type, {})

    # Same idempotency guard as `confirmation_free` — if the user
    # is already the manager of an active BW, just render the
    # confirmation page (no duplicate creation). Otherwise drop a
    # potentially-stale `session["bw_id"]` so the new BW resolves
    # cleanly post-creation. Ref: bug #0116.
    user = cast("User", g.user)
    existing = current_business_wall(user)
    if (
        existing is not None
        and existing.status != BWStatus.CANCELLED.value
        and is_bw_manager_or_admin(user, existing)
    ):
        # Bug #0071/2 : same DRAFT-stays-DRAFT trap as confirmation_free.
        # A paid BW pre-checkout sits in DRAFT until the Stripe webhook
        # flips it ; when the webhook fails (or doesn't exist, like in
        # recette), the user comes back here and the « Activation
        # Réussie » card lied. Flip the status here too so the gate on
        # /wip/opportunities/ stops blocking.
        if existing.status != BWStatus.ACTIVE.value:
            existing.status = BWStatus.ACTIVE.value  # type: ignore[assignment]
            # Link organisation to BW
            org = existing.get_organisation()
            if org:
                org.bw_id = existing.id
                org.bw_active = existing.bw_type
            db.session.commit()
        fill_session(existing)
        return render_template(
            "bw_activation/03_activation_payant_confirme.html",
            bw_type=bw_type,
            bw_info=bw_info,
        )
    session.pop("bw_id", None)

    # Security VULN-002 : in live mode the BW is created by the
    # `checkout.session.completed` webhook, not synchronously here.
    # The synchronous fallback is for the simulation flow only ; in
    # live mode it would let any caller who reaches this route (with
    # `bw_activated`/`bw_type` set via the simulation path or a forged
    # cookie) self-grant a paid BW for free.
    if current_app.config.get("STRIPE_LIVE_ENABLED"):
        return redirect(url_for("bw_activation.payment", bw_type=bw_type))

    # here create an actual BW instance
    created = create_new_paid_bw_record(session)
    warn("paid created", created)
    if created:
        # Commit the transaction now
        db_session = container.get(scoped_session)
        db_session.commit()

        # ensure  owner of the BW is member of the organisation
        user = cast("User", g.user)
        current_bw = current_business_wall(user)
        if current_bw is not None:
            fill_session(current_bw)
            org = current_bw.get_organisation()
            if org:
                change_members_emails(org, f"{user.email}")

        return render_template(
            "bw_activation/03_activation_payant_confirme.html",
            bw_type=bw_type,
            bw_info=bw_info,
        )

    return redirect(url_for("bw_activation.index"))
