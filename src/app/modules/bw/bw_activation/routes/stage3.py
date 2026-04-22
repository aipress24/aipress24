# Copyright (c) 2025, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Stage 3: Activation routes (free and paid)."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from flask import (
    current_app,
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
from app.modules.bw.bw_activation.config import BW_TYPES
from app.modules.bw.bw_activation.user_utils import current_business_wall
from app.services.stripe.utils import (
    get_stripe_public_key,
    load_pricing_table_id,
)

if TYPE_CHECKING:
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
    ctx: dict = {
        "bw_type": bw_type,
        "bw_info": bw_info,
        "pricing_value": session["pricing_value"],
        "stripe_live": False,
    }

    if current_app.config.get("STRIPE_LIVE_ENABLED"):
        draft_bw = _get_or_create_draft_bw_for_checkout(g.user, bw_type)
        if draft_bw is not None:
            ctx.update(
                {
                    "stripe_live": True,
                    "bw_id": str(draft_bw.id),
                    "pricing_table_id": load_pricing_table_id(bw_type),
                    "stripe_public_key": get_stripe_public_key(),
                    "user_email": g.user.email,
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
            draft_bw.name = request.form.get("company_name", "").strip()
            draft_bw.postal_address = request.form.get("postal_address", "").strip()
            draft_bw.tel_standard = request.form.get("tel_standard", "").strip()
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


def _get_or_create_draft_bw_for_checkout(user: User, bw_type: str):
    """Return a DRAFT Business Wall for this user/bw_type, creating one
    if none exists yet. Used as the target of the Stripe Pricing Table's
    `client-reference-id`.
    """
    from datetime import UTC, datetime

    from app.flask.extensions import db
    from app.modules.bw.bw_activation.models import (
        BusinessWall,
        BWStatus,
        Subscription,
        SubscriptionStatus,
    )

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
    """Simulate payment and activate paid BW."""
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
            org = current_bw.get_organisation()
            if org:
                change_members_emails(org, f"{user.email}")

        return render_template(
            "bw_activation/03_activation_payant_confirme.html",
            bw_type=bw_type,
            bw_info=bw_info,
        )

    return redirect(url_for("bw_activation.index"))
