# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Admin organization detail and management views.

This module provides the admin interface for inspecting and managing individual
organizations. Admins can view organization details, modify Business Wall settings,
manage membership (members, managers, leaders), and handle invitations.

The Business Wall form editing uses a session-based read-only flag to prevent
accidental modifications. Admins must explicitly enable edit mode, and the form
returns to read-only after saving or canceling.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import ClassVar, cast

import stripe
from flask import (
    Response,
    current_app,
    flash,
    g,
    redirect,
    render_template,
    request,
    url_for,
)
from flask.views import MethodView
from sqlalchemy import select
from stripe import StripeError

from app.enums import BWRoleType, InvitationStatus
from app.flask.extensions import db
from app.flask.lib.nav import nav
from app.flask.sqla import get_obj
from app.logging import report_failure, warn
from app.models.auth import User
from app.models.organisation import Organisation
from app.modules.admin import blueprint
from app.modules.admin.org_email_utils import (
    change_invitations_emails,
    change_members_emails,
)
from app.modules.admin.utils import (
    delete_full_organisation,
    gc_organisation,
    get_user_per_email,
    remove_user_organisation,
    set_user_organisation,
    toggle_org_active,
)
from app.modules.admin.views._show_org import OrgVM
from app.modules.bw.bw_activation.bw_cancellation import (
    cancel_business_wall_from_app,
)
from app.modules.bw.bw_activation.models import BusinessWall
from app.modules.bw.bw_activation.models.role import RoleAssignment
from app.modules.bw.bw_activation.user_utils import (
    get_active_business_wall_for_organisation,
)
from app.modules.bw.bw_activation.utils import fill_session, is_bw_manager_or_admin
from app.services.stripe.product import resolve_product_price
from app.services.stripe.utils import attr_or_item_getter, load_stripe_api_key


class ShowOrgView(MethodView):
    """Organization detail page with management actions."""

    decorators: ClassVar[list] = [
        nav(parent="orgs", icon="clipboard-document-check", label="Détail organisation")
    ]

    def get(self, uid: str):
        """Display the admin detail page for a single organization.

        The page shows organization info, membership lists, and BW management options.
        """
        org = get_obj(uid, Organisation)
        active_bw = get_active_business_wall_for_organisation(org)
        current_owner_email = ""
        current_owner_id = None
        current_owner_full_name = ""
        if active_bw:
            current_owner = db.session.get(User, active_bw.owner_id)
            current_owner_email = current_owner.email if current_owner else ""
            current_owner_id = current_owner.id if current_owner else None
            current_owner_full_name = current_owner.full_name if current_owner else ""

        bw_missing_stripe_sub = bool(
            active_bw
            and (
                active_bw.subscription is None
                or not active_bw.subscription.stripe_subscription_id
            )
        )

        return render_template(
            "admin/pages/show_org.j2",
            title="Informations sur l'organisation",
            org=OrgVM(org),
            current_owner_email=current_owner_email,
            current_owner_id=current_owner_id,
            current_owner_full_name=current_owner_full_name,
            bw_missing_stripe_sub=bw_missing_stripe_sub,
        )

    def post(self, uid: str) -> Response:
        """Process admin actions on an organization.

        Handles multiple HTMX-triggered actions via the "action" form field:
        - BW form mode toggling (allow_modify_bw, cancel_modification_bw,
          validate_modification_bw)
        - Organization lifecycle (toggle_org_active, delete_org)
        - Membership management (change_emails)
        - Invitation management (change_invitations_emails)

        All actions respond with HX-Redirect headers so HTMX performs a client-side
        redirect, ensuring the page reflects the updated state. The gc_organisation
        check after changing members handles cleanup if the org becomes empty.
        """
        org = get_obj(uid, Organisation)
        action = request.form.get("action", "")
        current_url = url_for("admin.show_org", uid=uid)
        orgs_url = url_for("admin.orgs")

        response = Response("")

        match action:
            case "toggle_org_active":
                toggle_org_active(org)
                response.headers["HX-Redirect"] = current_url

            case "deactivate_bw":
                active_bw = get_active_business_wall_for_organisation(org)
                if active_bw:
                    result = cancel_business_wall_from_app(active_bw, commit=False)
                    if result.get("success"):
                        flash(
                            f"Le Business Wall a été désactivé. "
                            f"{result.get('cleared_users_count', 0)} utilisateur(s) mis à jour.",
                            "success",
                        )
                    else:
                        flash(
                            f"Échec de la désactivation : {result.get('reason')}",
                            "error",
                        )
                response.headers["HX-Redirect"] = current_url

            case "delete_org":
                if error := delete_full_organisation(org):
                    flash(error, "error")
                    response.headers["HX-Redirect"] = current_url
                else:
                    change_invitations_emails(org, "")
                    response.headers["HX-Redirect"] = orgs_url

            case "change_emails":
                raw_mails = request.form["content"]
                active_bw = get_active_business_wall_for_organisation(org)
                if active_bw:
                    self._change_bw_members_emails(active_bw, raw_mails)
                else:
                    change_members_emails(org, raw_mails)

                if gc_organisation(org):
                    response.headers["HX-Redirect"] = orgs_url
                else:
                    response.headers["HX-Redirect"] = current_url

            case "change_invitations_emails":
                raw_mails = request.form["content"]
                change_invitations_emails(org, raw_mails)
                response.headers["HX-Redirect"] = current_url

            case "change_bw_invitations_emails":
                raw_mails = request.form["content"]
                active_bw = get_active_business_wall_for_organisation(org)
                if active_bw:
                    self._change_bw_invitations_emails(active_bw, raw_mails)
                response.headers["HX-Redirect"] = current_url

            case _:
                response.headers["HX-Redirect"] = orgs_url

        db.session.commit()
        return response

    def _change_bw_members_emails(self, bw: BusinessWall, raw_mails: str) -> None:
        org = bw.get_organisation()
        if not org:
            return

        owner = db.session.get(User, bw.owner_id)
        owner_mail = owner.email if owner else ""

        updated_mails = {m.lower() for m in raw_mails.split()}
        if owner_mail:
            updated_mails.add(owner_mail.lower())

        bw_members_ids = list(
            db.session.scalars(
                select(RoleAssignment.user_id)
                .where(RoleAssignment.business_wall_id == bw.id)
                .where(
                    RoleAssignment.invitation_status == InvitationStatus.ACCEPTED.value
                )
            ).all()
        )
        # always keep the BW owner in BW members
        if bw.owner_id and bw.owner_id not in bw_members_ids:
            bw_members_ids.append(bw.owner_id)

        previous_emails = set()
        if bw_members_ids:
            previous_emails = {
                u.email.lower()
                for u in db.session.scalars(
                    select(User).where(User.id.in_(bw_members_ids))
                ).all()
                if u.email
            }

        # Remove members set (by difference)
        mails_to_remove = {
            m
            for m in previous_emails
            if m not in updated_mails and m != owner_mail.lower()
        }
        for mail in mails_to_remove:
            user = get_user_per_email(mail)
            if user:
                remove_user_organisation(user)
                db.session.execute(
                    db.delete(RoleAssignment)
                    .where(RoleAssignment.business_wall_id == bw.id)
                    .where(RoleAssignment.user_id == user.id)
                )

        # Add new members
        mails_to_add = {m for m in updated_mails if m not in previous_emails}
        for mail in mails_to_add:
            user = get_user_per_email(mail)
            if user:
                set_user_organisation(user, org)
                existing_role = db.session.scalar(
                    select(RoleAssignment).where(
                        RoleAssignment.business_wall_id == bw.id,
                        RoleAssignment.user_id == user.id,
                        RoleAssignment.role_type == "",
                    )
                )
                if existing_role:
                    # mimic the acceptance if already invited
                    existing_role.invitation_status = InvitationStatus.ACCEPTED.value
                    existing_role.accepted_at = datetime.now(UTC)

    def _change_bw_invitations_emails(self, bw: BusinessWall, raw_mails: str) -> None:
        org = bw.get_organisation()
        if not org:
            return

        updated_mails = {m.lower() for m in raw_mails.split()}

        bw_pending_ids = list(
            db.session.scalars(
                select(RoleAssignment.user_id)
                .where(RoleAssignment.business_wall_id == bw.id)
                .where(
                    RoleAssignment.invitation_status == InvitationStatus.PENDING.value
                )
                .where(RoleAssignment.role_type == "")
            ).all()
        )
        previous_pending_emails = set()
        if bw_pending_ids:
            previous_pending_emails = {
                u.email.lower()
                for u in db.session.scalars(
                    select(User).where(User.id.in_(bw_pending_ids))
                ).all()
                if u.email
            }

        # Remove pending invitations
        mails_to_remove = previous_pending_emails - updated_mails
        for mail in mails_to_remove:
            user = get_user_per_email(mail)
            if user:
                db.session.execute(
                    db.delete(RoleAssignment)
                    .where(RoleAssignment.business_wall_id == bw.id)
                    .where(RoleAssignment.user_id == user.id)
                    .where(RoleAssignment.role_type == "")
                    .where(
                        RoleAssignment.invitation_status
                        == InvitationStatus.PENDING.value
                    )
                )

        # Add new pending invitations
        mails_to_add = updated_mails - previous_pending_emails
        for mail in mails_to_add:
            user = get_user_per_email(mail)
            if user:
                set_user_organisation(user, org)
                db.session.add(
                    RoleAssignment(
                        business_wall_id=bw.id,
                        user_id=user.id,
                        role_type="",
                        invitation_status=InvitationStatus.PENDING.value,
                        invited_at=datetime.now(UTC),
                    )
                )


# Register the view
blueprint.add_url_rule("/show_org/<uid>", view_func=ShowOrgView.as_view("show_org"))


@blueprint.route("/show_org/<uid>/change_bw_owner", methods=["GET", "POST"])
@nav(parent="orgs", icon="clipboard-document-check", label="Changer le BW owner")
def change_bw_owner(uid: str):
    """Admin page to change the Business Wall owner of an organisation.

    GET shows a form pre-filled with the current owner email.
    POST validates the new email, resolves it to a registered user,
    updates the active BusinessWall owner_id, ensures the new user has
    an accepted BW_OWNER role assignment.
    """
    org = get_obj(uid, Organisation)
    active_bw = get_active_business_wall_for_organisation(org)
    if active_bw is None:
        flash("Aucun Business Wall actif pour cette organisation.", "error")
        return redirect(url_for("admin.show_org", uid=uid))

    current_owner = db.session.get(User, active_bw.owner_id)
    current_owner_email = current_owner.email if current_owner else ""

    if request.method == "POST":
        new_email = request.form.get("new_owner_email", "").strip()
        if not new_email:
            flash("Veuillez saisir une adresse email.", "error")
            return redirect(url_for("admin.change_bw_owner", uid=uid))

        new_owner = get_user_per_email(new_email)
        if new_owner is None:
            flash(
                f"Aucun utilisateur inscrit trouvé avec l'email '{new_email}'.",
                "error",
            )
            return redirect(url_for("admin.change_bw_owner", uid=uid))

        if new_owner.id == active_bw.owner_id:
            flash(
                "Le nouvel utilisateur est déjà le propriétaire du Business Wall.",
                "info",
            )
            return redirect(url_for("admin.show_org", uid=uid))

        # Refuse if the target user already is owner of another Business Wall.
        other_bw_stmt = select(BusinessWall).where(
            BusinessWall.owner_id == new_owner.id,
            BusinessWall.id != active_bw.id,
        )
        if db.session.scalar(other_bw_stmt):
            flash(
                (
                    f"{new_owner.email} est déjà propriétaire d'un autre Business Wall. "
                    "Un utilisateur ne peut pas être propriétaire de plusieurs Business Walls."
                ),
                "error",
            )
            return redirect(url_for("admin.change_bw_owner", uid=uid))

        # Move the new owner into the BW's organisation.
        if new_owner.organisation_id != org.id:
            error = set_user_organisation(new_owner, org)
            if error:
                flash(
                    f"Impossible de rattacher le nouvel utilisateur à l'organisation : {error}",
                    "error",
                )
                return redirect(url_for("admin.change_bw_owner", uid=uid))

        previous_owner_id = active_bw.owner_id

        active_bw.owner_id = new_owner.id
        if active_bw.payer_is_owner:
            active_bw.payer_id = new_owner.id

        # Ensure the new owner has an accepted BW_OWNER role assignment.
        existing_owner_role = db.session.scalar(
            select(RoleAssignment).where(
                RoleAssignment.business_wall_id == active_bw.id,
                RoleAssignment.user_id == new_owner.id,
                RoleAssignment.role_type == BWRoleType.BW_OWNER.value,
            )
        )
        if existing_owner_role:
            existing_owner_role.invitation_status = InvitationStatus.ACCEPTED.value
        else:
            db.session.add(
                RoleAssignment(
                    business_wall_id=active_bw.id,
                    user_id=new_owner.id,
                    role_type=BWRoleType.BW_OWNER.value,
                    invitation_status=InvitationStatus.ACCEPTED.value,
                    accepted_at=datetime.now(UTC),
                )
            )

        # Remove the previous owner BW_OWNER role assignment
        previous_owner_role = db.session.scalar(
            select(RoleAssignment).where(
                RoleAssignment.business_wall_id == active_bw.id,
                RoleAssignment.user_id == previous_owner_id,
                RoleAssignment.role_type == BWRoleType.BW_OWNER.value,
            )
        )
        if previous_owner_role:
            db.session.delete(previous_owner_role)

        db.session.commit()
        flash(
            f"Le propriétaire du Business Wall a été changé pour {new_owner.email}.",
            "success",
        )
        return redirect(url_for("admin.show_org", uid=uid))

    return render_template(
        "admin/pages/show_org_change_bw_owner.j2",
        title="Changer le BW owner du BW",
        org=org,
        active_bw=active_bw,
        current_owner_email=current_owner_email,
    )


@blueprint.route("/show_org/<uid>/bw-dashboard", methods=["GET"])
@nav(parent="orgs", icon="clipboard-document-check", label="Gérer le BW")
def admin_bw_dashboard(uid: str):
    """Admin access to a specific org's BW dashboard.

    Switches the admin user's session to the active BW of the given
    organisation, then redirects to the BW dashboard.
    """
    org = get_obj(uid, Organisation)
    active_bw = get_active_business_wall_for_organisation(org)
    if active_bw is None:
        flash("Aucun Business Wall actif pour cette organisation.", "error")
        return redirect(url_for("admin.show_org", uid=uid))

    user = cast(User, g.user)

    # Admins bypass manager checks, but still need a valid management path.
    fill_session(active_bw)
    if not is_bw_manager_or_admin(user, active_bw):
        # Persist an accepted BW_OWNER role assignment for the admin so
        # the dashboard guard passes. This is the admin override path.
        existing = db.session.scalar(
            select(RoleAssignment).where(
                RoleAssignment.business_wall_id == active_bw.id,
                RoleAssignment.user_id == user.id,
                RoleAssignment.role_type == BWRoleType.BW_OWNER.value,
            )
        )
        if existing is None:
            db.session.add(
                RoleAssignment(
                    business_wall_id=active_bw.id,
                    user_id=user.id,
                    role_type=BWRoleType.BW_OWNER.value,
                    invitation_status=InvitationStatus.ACCEPTED.value,
                )
            )
        else:
            existing.invitation_status = InvitationStatus.ACCEPTED.value
        db.session.commit()
        fill_session(active_bw)

    return redirect(url_for("bw_activation.dashboard"))


@blueprint.route("/show_org/<uid>/resubscribe-stripe", methods=["POST"])
def admin_resubscribe_stripe(uid: str):
    """Redirect admin directly to Stripe Checkout for an active BW missing a Stripe sub."""

    from app.modules.bw.bw_activation.bw_product import (
        allowed_bw_product_list,
        select_product_for_quantity,
    )
    from app.modules.bw.bw_activation.config import employee_count_from_taille_orga
    from app.modules.bw.bw_activation.routes.stage3 import (
        _add_billing_collection,
        _build_checkout_metadata,
        _create_stripe_checkout_session,
        _resolve_stripe_customer_kwargs_for_payer,
    )

    org = get_obj(uid, Organisation)
    active_bw = get_active_business_wall_for_organisation(org)
    if active_bw is None:
        flash("Aucun Business Wall actif pour cette organisation.", "error")
        return redirect(url_for("admin.show_org", uid=uid))

    if (
        active_bw.subscription is not None
        and active_bw.subscription.stripe_subscription_id
    ):
        flash("Ce Business Wall possède déjà un abonnement Stripe.", "info")
        return redirect(url_for("admin.show_org", uid=uid))

    if not load_stripe_api_key():
        flash("Stripe n'est pas configuré sur cette instance.", "error")
        return redirect(url_for("admin.show_org", uid=uid))

    allowed_products = allowed_bw_product_list(active_bw.bw_type)
    if not allowed_products:
        flash(
            f"Aucune offre Stripe disponible pour le type {active_bw.bw_type}.",
            "error",
        )
        return redirect(url_for("admin.show_org", uid=uid))

    taille_orga = active_bw.taille_orga or getattr(org, "taille_orga", "") or ""
    quantity = max(
        1, employee_count_from_taille_orga(taille_orga) if taille_orga else 1
    )
    chosen_product = select_product_for_quantity(allowed_products, quantity)
    price_id, default_price = resolve_product_price(chosen_product)
    if not price_id:
        flash("Aucun tarif Stripe trouvé pour ce Business Wall.", "error")
        return redirect(url_for("admin.show_org", uid=uid))

    if isinstance(default_price, dict):
        billing_scheme = default_price.get("billing_scheme")
    else:
        billing_scheme = getattr(default_price, "billing_scheme", None)
    checkout_quantity = quantity if billing_scheme == "tiered" else 1

    owner = db.session.get(User, active_bw.owner_id) if active_bw.owner_id else None
    payer_email = (
        active_bw.payer_email
        or (owner.email if owner else None)
        or cast(User, g.user).email
    )

    base_success_url = url_for(
        "admin.admin_resubscribe_stripe_success",
        uid=uid,
        _external=True,
    )
    success_url = f"{base_success_url}?session_id={{CHECKOUT_SESSION_ID}}"
    cancel_url = url_for("admin.show_org", uid=uid, _external=True)

    checkout_kwargs: dict[str, object] = {
        "mode": "subscription",
        "line_items": [{"price": price_id, "quantity": checkout_quantity}],
        "success_url": success_url,
        "cancel_url": cancel_url,
        "client_reference_id": str(active_bw.id),
        "metadata": _build_checkout_metadata(
            active_bw.id, active_bw.bw_type, active_bw.owner_id
        ),
        "automatic_tax": {"enabled": True},
        "allowed_payment_method_types": ["card"],
    }
    checkout_kwargs.update(
        _resolve_stripe_customer_kwargs_for_payer(org.stripe_customer_id, payer_email)
    )
    _add_billing_collection(checkout_kwargs)

    try:
        checkout_session = _create_stripe_checkout_session(
            checkout_kwargs, org, payer_email
        )
    except StripeError as exc:
        warn(f"Admin resubscribe Stripe failed for BW {active_bw.id}: {exc}")
        report_failure(f"Admin resubscribe Stripe failed ({active_bw.bw_type})", exc)
        flash(
            "La session Stripe n'a pas pu être créée.",
            "error",
        )
        return redirect(url_for("admin.show_org", uid=uid))

    return redirect(checkout_session.url, code=303)


@blueprint.route("/show_org/<uid>/resubscribe-stripe/success", methods=["GET"])
def admin_resubscribe_stripe_success(uid: str):
    """Attach the new Stripe subscription to the active BW on Checkout return."""

    from app.modules.bw.bw_activation.activate_bw import activate_bw_from_checkout

    org = get_obj(uid, Organisation)
    active_bw = get_active_business_wall_for_organisation(org)
    session_id = (request.args.get("session_id") or "").strip()

    if (
        active_bw is not None
        and session_id
        and "{CHECKOUT_SESSION_ID}" not in session_id
        and not current_app.config.get("STRIPE_DEBUG_ACTIVE")
    ):
        load_stripe_api_key()
        try:
            checkout_session = stripe.checkout.Session.retrieve(session_id)
        except StripeError as exc:
            warn(f"admin_resubscribe_stripe_success: {exc}")
            checkout_session = None

        if checkout_session is not None:
            get = attr_or_item_getter(checkout_session)
            if (
                get("mode") == "subscription"
                and get("status") == "complete"
                and get("payment_status") in ("paid", "no_payment_required")
                and str(get("client_reference_id") or "") == str(active_bw.id)
            ):
                activate_bw_from_checkout(
                    bw=active_bw,
                    customer_id=str(get("customer") or ""),
                    subscription_id=str(get("subscription") or ""),
                    checkout_session_id=session_id,
                )
                db.session.commit()
                flash(
                    "L'abonnement Stripe du Business Wall a été recréé.",
                    "success",
                )
                return redirect(url_for("admin.show_org", uid=uid))

    flash("Paiement validé. L'abonnement Stripe est en cours de liaison.", "info")
    return redirect(url_for("admin.show_org", uid=uid))
