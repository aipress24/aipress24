# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Organization invitations preferences view."""

from __future__ import annotations

from typing import Any, cast

from flask import Response, flash, g, redirect, render_template, request
from flask.views import MethodView
from sqlalchemy import func, select

from app.flask.extensions import db
from app.flask.routing import url_for
from app.flask.sqla import get_obj
from app.models.auth import User
from app.models.invitation import Invitation
from app.models.organisation import Organisation
from app.modules.admin.utils import gc_all_auto_organisations, set_user_organisation
from app.modules.bw.bw_activation.bw_invitation import BW_ROLE_TYPE_LABEL
from app.modules.bw.bw_activation.models import (
    BusinessWall,
    InvitationStatus,
    Partnership,
    PartnershipStatus,
    RoleAssignment,
)
from app.modules.bw.bw_activation.models.business_wall import BWStatus
from app.modules.preferences import blueprint
from app.ui.labels import LABELS_BW_TYPE_V2

# ── Pure helpers ──────────────────────────────────────────────────────
#
# Extracted from `InvitationsView` so they can be unit-tested without
# a DB session. See `tests/a_unit/modules/preferences/test_invitation_helpers.py`.


def normalise_email(value: str | None) -> str:
    """Lowercase + strip whitespace ; None becomes empty string.

    Both the listing query and the `_join_organisation` security
    guard use this to compare the user's email against the
    `Invitation.email` column. The DB-side comparison uses
    `func.lower(func.trim(...))` ; this Python-side helper must
    produce the same key, otherwise an invitation shown in the UI
    couldn't be accepted because the join gate would refuse it.
    """
    return (value or "").strip().lower()


def count_open_invitations(invitations_list) -> int:
    """Count invitations whose `disabled` flag is empty (i.e. the
    user CAN still accept them — `disabled == "disabled"` means
    they're already a member). Pin so the « open count » bubble in
    the UI stays accurate after refactors of the list shape."""
    return sum(1 for i in invitations_list if i.get("disabled") == "")


def parse_partnership_id(raw: str | None):
    """Safely parse a partnership UUID from a form field.

    Returns the `UUID` object on success, None on missing/blank/
    non-UUID input. Mirrors `parse_org_id`'s silent-refusal contract
    so the `ack_revoked_partnership` POST handler never raises on
    crafted form input."""
    from uuid import UUID

    if not raw:
        return None
    try:
        return UUID(raw)
    except (TypeError, ValueError):
        return None


def parse_org_id(raw: str | None) -> int | None:
    """Safely parse an org id from a form field.

    Returns None when the value is missing, blank, or non-integer
    (« silent refusal » policy : the gate avoids leaking whether the
    org id exists at all). Previously `_join_organisation` raised
    ValueError on non-numeric input, leaking a 500.
    """
    if not raw:
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def format_org_label(org) -> str:
    """Build the display label for an organisation in the invitations
    listing.

    - org with an active BusinessWall : `« <bw_name> (<bw_type_label>) »`
      where the type label comes from `LABELS_BW_TYPE_V2` (falls back
      to the raw bw_active code if the labels dict doesn't know it).
    - org without a BW : just the plain organisation name.

    Duck-typed on `org` — only reads `name`, `bw_id`, `bw_name`,
    `bw_active`. Unit-testable without a real Organisation row.
    """
    if org.bw_id:
        # pyrefly: ignore [no-matching-overload]
        return f"{org.bw_name} ({LABELS_BW_TYPE_V2.get(org.bw_active, org.bw_active)})"
    return f"{org.name}"


def _bw_display_name(business_wall) -> str:
    """Safe display name for a BusinessWall — falls back to a marker
    string if `name_safe` is empty / None so the UI never renders a
    bare empty space."""
    return business_wall.name_safe or "(Nom inconnu)"


def role_invitation_to_dict(role_assignment, business_wall) -> dict[str, Any]:
    """Map a `(RoleAssignment, BusinessWall)` query row to the dict
    shape consumed by the `org_invitation.j2` template. Pure
    transformation : no DB, no Flask context."""
    return {
        "id": str(role_assignment.id),
        "bw_id": str(business_wall.id),
        "bw_name": _bw_display_name(business_wall),
        "role_type": role_assignment.role_type,
        "role_label": BW_ROLE_TYPE_LABEL.get(
            role_assignment.role_type, role_assignment.role_type
        ),
        "user_id": role_assignment.user_id,
        "invited_at": role_assignment.invited_at,
    }


def accepted_role_to_dict(role_assignment, business_wall) -> dict[str, Any]:
    """Companion of `role_invitation_to_dict` for the « accepted
    roles » section. Shape differs slightly : `accepted_at` instead of
    `invited_at` and `user_id` is omitted (the row is the user's own)."""
    return {
        "id": str(role_assignment.id),
        "bw_id": str(business_wall.id),
        "bw_name": _bw_display_name(business_wall),
        "role_type": role_assignment.role_type,
        "role_label": BW_ROLE_TYPE_LABEL.get(
            role_assignment.role_type, role_assignment.role_type
        ),
        "accepted_at": role_assignment.accepted_at,
    }


def partnership_invitation_to_dict(partnership, business_wall) -> dict[str, Any]:
    """Map a pending `Partnership` row to the dict consumed by the
    « partnership invitations » section. The `role_label` is hardcoded
    because every partnership maps to the same external role (PR
    Manager (external))."""
    return {
        "id": str(partnership.id),
        "bw_id": str(business_wall.id),
        "bw_name": _bw_display_name(business_wall),
        "role_label": "PR Manager (external)",
        "invited_at": partnership.invited_at,
    }


def resolve_client_name(business_wall, client_org) -> str:
    """Pick the display name for the client side of a partnership.

    Prefer the live `Organisation.name` ; fall back to the BW's safe
    name ; finally to a marker so the row still renders. Used by the
    REVOKED-partnerships list (ticket #0169 part 3)."""
    if client_org is not None:
        return client_org.name
    return business_wall.name_safe or "(client inconnu)"


def revoked_partnership_to_dict(
    partnership, business_wall, client_org
) -> dict[str, Any]:
    """Map a REVOKED `Partnership` row to the dict consumed by the
    « partnerships terminated » section."""
    return {
        "id": str(partnership.id),
        "bw_name": _bw_display_name(business_wall),
        "client_name": resolve_client_name(business_wall, client_org),
        "revoked_at": partnership.revoked_at,
    }


class InvitationsView(MethodView):
    """invitations d'organisations"""

    def get(self):
        user = cast(User, g.user)
        invitations_list = self._organisation_inviting(user)
        open_invitations = count_open_invitations(invitations_list)
        role_invitations_list = self._role_invitations(user)
        accepted_roles_list = self._accepted_role_invitations(user)
        partnership_invitations_list = self._partnership_invitations(user)
        revoked_partnerships_list = self._revoked_partnerships(user)
        ctx = {
            "invitations": invitations_list,
            "open_invitations": open_invitations,
            "role_invitations": role_invitations_list,
            "open_role_invitations": len(role_invitations_list),
            "accepted_roles": accepted_roles_list,
            "open_accepted_roles": len(accepted_roles_list),
            "partnership_invitations": partnership_invitations_list,
            "open_partnership_invitations": len(partnership_invitations_list),
            "revoked_partnerships": revoked_partnerships_list,
            "open_revoked_partnerships": len(revoked_partnerships_list),
            "title": "Invitation d'organisation",
        }
        return render_template("pages/preferences/org_invitation.j2", **ctx)

    def post(self):
        action = request.form["action"]
        match action:
            case "join_org":
                org_id = request.form["target"]
                user = g.user
                self._join_organisation(user, org_id)
                response = Response("")
                response.headers["HX-Redirect"] = url_for(".invitations")
            case "ack_revoked_partnership":
                # Ticket #0169 part 3 : user clicked « Confirmer » on a
                # revoked partnership row → hard-delete the Partnership
                # row so the line disappears from the list. Matches
                # Erick's « éliminer cette ligne ».
                user = cast(User, g.user)
                self._ack_revoked_partnership(
                    user, request.form.get("partnership_id", "")
                )
                flash(
                    "Votre confirmation de fin de partenariat est bien enregistrée.",
                    "success",
                )
                # Ticket #0169: this button is a plain <form> POST (not htmx),
                # so an HX-Redirect header is ignored and the browser renders
                # the empty body as a blank page. A real 302 is followed
                # natively and the success flash shows on the GET.
                response = redirect(url_for(".invitations"))
            case _:
                response = Response("")
                response.headers["HX-Redirect"] = url_for(".home")
        return response

    def _ack_revoked_partnership(self, user: User, partnership_id: str) -> None:
        """Hard-delete a REVOKED partnership the user's org is the
        partner of (ticket #0169 part 3)."""
        pid = parse_partnership_id(partnership_id)
        if pid is None:
            return
        org = user.organisation
        if org is None:
            return
        # Find every BW tied to this user's organisation — the row to
        # ack lives in `partner_bw_id` of a REVOKED Partnership whose
        # `business_wall_id` is on the client side.
        db_session = db.session
        stmt = select(BusinessWall.id).where(BusinessWall.organisation_id == org.id)
        bw_ids = {str(bw_id) for bw_id in db_session.scalars(stmt)}
        if not bw_ids:
            return
        partnership = db_session.get(Partnership, pid)
        if partnership is None:
            return
        # Only the partner side (PR Agency) can ack — the *client* side
        # owns the row and shouldn't delete its own revoke trail this way.
        if partnership.partner_bw_id not in bw_ids:
            return
        if partnership.status != PartnershipStatus.REVOKED.value:
            return
        db_session.delete(partnership)
        db_session.commit()

    def _organisation_inviting(self, user: User) -> list[dict[str, Any]]:
        """Get list of organizations that have invited this user."""
        db_session = db.session
        # Bug 0130: normalise both sides (strip + lower) so an invitation
        # whose email was stored with stray whitespace or uppercase still
        # surfaces in the invitee's preferences page.
        normalised = normalise_email(user.email)
        stmt = select(Invitation).where(
            func.lower(func.trim(Invitation.email)) == normalised
        )
        invitations = db_session.scalars(stmt)
        invit_ids = {i.organisation_id for i in invitations}

        # Current organisation: always show it if it exists.
        result = []
        if user.organisation:
            user_org = user.organisation
            result.append(
                {
                    "label": format_org_label(user_org),
                    "org_id": str(user_org.id),
                    "disabled": "disabled",
                }
            )
            # Remove from invitations if present
            invit_ids.discard(user_org.id)

        if invit_ids:
            stmt = (
                select(Organisation)
                .where(Organisation.deleted_at.is_(None))
                .filter(Organisation.id.in_(list(invit_ids)))
            )
            organisations = db_session.scalars(stmt)
            for org in organisations:
                result.append(
                    {
                        "label": format_org_label(org),
                        "org_id": str(org.id),
                        "disabled": "",
                    }
                )
        return result

    def _role_invitations(self, user: User) -> list[dict[str, Any]]:
        """Return the list of pending BusinessWall role invitations for this user.

        Bug #0139 (constat B) : ne lister que les rôles attachés à un
        BW *actif* — sans ce filtre, les rôles d'itérations antérieures
        (BWs cancelled/recréés) ressurgissaient comme duplicats fantômes.
        """
        db_session = db.session
        stmt = (
            select(RoleAssignment, BusinessWall)
            .join(BusinessWall, RoleAssignment.business_wall_id == BusinessWall.id)
            .where(
                RoleAssignment.user_id == user.id,
                RoleAssignment.invitation_status == InvitationStatus.PENDING.value,
                BusinessWall.status == BWStatus.ACTIVE.value,
            )
        )
        results = db_session.execute(stmt).all()

        return [
            role_invitation_to_dict(role_assignment, business_wall)
            for role_assignment, business_wall in results
        ]

    def _accepted_role_invitations(self, user: User) -> list[dict[str, Any]]:
        """Return the BusinessWall roles this user has accepted.

        Bug: an accepted role (e.g. BWPRi) disappeared from this page
        because only PENDING assignments were listed, so the user thought
        the role had been lost. Accepted roles must stay visible.

        Bug #0139 (constat B) : filtrer sur BW actif uniquement — un
        rôle accepté sur un BW cancelled (itération antérieure d'un BW
        recréé depuis) ne doit plus apparaître. Cela neutralise aussi
        d'éventuels rôles legacy hérités d'avant le fix `stage3.py`
        (BWO non sollicité de Lorraine, etc.).
        """
        db_session = db.session
        stmt = (
            select(RoleAssignment, BusinessWall)
            .join(BusinessWall, RoleAssignment.business_wall_id == BusinessWall.id)
            .where(
                RoleAssignment.user_id == user.id,
                RoleAssignment.invitation_status == InvitationStatus.ACCEPTED.value,
                BusinessWall.status == BWStatus.ACTIVE.value,
            )
        )
        results = db_session.execute(stmt).all()

        return [
            accepted_role_to_dict(role_assignment, business_wall)
            for role_assignment, business_wall in results
        ]

    def _partnership_invitations(self, user: User) -> list[dict[str, Any]]:
        """Return the list of pending BusinessWall partnership invitations for this user.

        Partnership invitations are sent to a PR Agency's BusinessWall owner
        to become an external PR Manager for another BusinessWall.

        Bug #0123: previously this only looked at `org.bw_id` (the active BW).
        If the agency had not activated its BW yet, or if `bw_id` was stale,
        the invitation was invisible. Now we search across all BWs that
        belong to the user's organisation.
        """
        db_session = db.session
        org = user.organisation
        if not org:
            return []

        # Find every BW tied to this organisation (not just the active one).
        stmt = select(BusinessWall).where(BusinessWall.organisation_id == org.id)
        org_bws = list(db_session.scalars(stmt))
        if not org_bws:
            return []

        bw_ids = [str(bw.id) for bw in org_bws]
        stmt = (
            select(Partnership, BusinessWall)
            .join(BusinessWall, Partnership.business_wall_id == BusinessWall.id)
            .where(
                Partnership.partner_bw_id.in_(bw_ids),
                Partnership.status == PartnershipStatus.INVITED.value,
            )
        )
        results = db_session.execute(stmt).all()

        return [
            partnership_invitation_to_dict(partnership, business_wall)
            for partnership, business_wall in results
        ]

    def _revoked_partnerships(self, user: User) -> list[dict[str, Any]]:
        """Return REVOKED partnerships where the user's organisation
        is the partner (i.e. the PR Agency whose client revoked the
        partnership). Ticket #0169 part 3 — Erick : « Indiquer dans
        PROFIL/PRÉFÉRENCES/Invitations d'organisations [...] la fin
        du partenariat [...] avec un bouton "Confirmer" qui conduira
        à éliminer cette ligne ».
        """
        db_session = db.session
        org = user.organisation
        if not org:
            return []

        stmt = select(BusinessWall).where(BusinessWall.organisation_id == org.id)
        org_bws = list(db_session.scalars(stmt))
        if not org_bws:
            return []

        bw_ids = [str(bw.id) for bw in org_bws]
        stmt = (
            select(Partnership, BusinessWall)
            .join(BusinessWall, Partnership.business_wall_id == BusinessWall.id)
            .where(
                Partnership.partner_bw_id.in_(bw_ids),
                Partnership.status == PartnershipStatus.REVOKED.value,
            )
            .order_by(Partnership.revoked_at.desc())
        )
        results = db_session.execute(stmt).all()

        return [
            revoked_partnership_to_dict(
                partnership, business_wall, business_wall.get_organisation()
            )
            for partnership, business_wall in results
        ]

    def _join_organisation(self, user: User, org_id: str) -> None:
        """Join the specified organization.

        Security VERIFY-001 : require a matching `Invitation` row
        before mutating `user.organisation`. The list of joinable orgs
        in `_organisation_inviting` is invitation-filtered, but the
        POST handler used to trust whatever `target` the form sent —
        any authenticated user could POST an arbitrary org id and
        become a member. Mirror the same normalisation as the listing
        helper (lower + trim) so legacy whitespace/casing matches.
        """
        normalised = normalise_email(user.email)
        target_org_id = parse_org_id(org_id)
        if not normalised or target_org_id is None:
            return
        invitation = db.session.scalar(
            select(Invitation).where(
                func.lower(func.trim(Invitation.email)) == normalised,
                Invitation.organisation_id == target_org_id,
            )
        )
        if invitation is None:
            # No invitation : silently refuse — matches the listing
            # filter and avoids leaking whether the org id exists.
            return

        organisation = get_obj(org_id, Organisation)
        set_user_organisation(user, organisation)
        gc_all_auto_organisations()
        db.session.commit()


# Register the view
blueprint.add_url_rule("/invitations", view_func=InvitationsView.as_view("invitations"))
