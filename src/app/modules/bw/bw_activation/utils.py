# Copyright (c) 2025, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Utility functions for Business Wall activation workflow."""

from __future__ import annotations

from typing import Any, cast
from uuid import UUID

from flask import g, session
from sqlalchemy.exc import SQLAlchemyError
from svcs.flask import container

from app.enums import RoleEnum
from app.flask.extensions import db
from app.flask.sqla import get_obj
from app.logging import warn
from app.models.auth import User
from app.modules.bw.bw_activation.models import (
    BusinessWall,
    BusinessWallService,
    BWRoleType,
    BWStatus,
    BWType,
    InvitationStatus,
    PartnershipStatus,
    PermissionType,
)

# from app.modules.bw.bw_activation.models.repositories import BusinessWallRepository

ERR_NOT_MANAGER = (
    "Votre identification ne semble pas permettre la gestion de ce Business Wall."
)
ERR_BW_NOT_FOUND = "Aucun Business Wall trouvé."
ERR_NO_ORGANISATION = "Aucune organisation trouvée pour le Business Wall."
# Ticket 0271 : a user who left their organisation has no organisation
# left, and leaving also cleared the organisation name from their KYC.
# Nothing else in the funnel collects one, so the activation used to die
# at the payment step with an opaque « aucune organisation » message.
ERR_ORGANISATION_NOT_DECLARED = (
    "Un Business Wall est rattaché à une organisation, et la vôtre n'est pas "
    "renseignée. Indiquez le nom de votre organisation dans votre profil, "
    "puis revenez activer votre Business Wall."
)
ERR_UNKNOWN_ACTION = "Erreur interne, action inconnue."
# Ticket 0273 : students reached the « Business Wall for Journalist »
# funnel. The subscription belongs to the school, not to its students.
ERR_PROFILE_NOT_ELIGIBLE = (
    "L'abonnement Business Wall est réservé aux établissements et aux "
    "professionnels. En tant qu'étudiant ou doctorant, rapprochez-vous de "
    "votre établissement : c'est lui qui souscrit un Business Wall for "
    "Academics, dont vous bénéficiez ensuite."
)
ERR_WRONG_VALIDATION_LINK = "Lien de validation erroné."
ERR_INVITATION_NOT_FOUND = "Invitation non trouvée."


def is_bw_manager_or_admin(user: User, bw: BusinessWall) -> bool:
    """Check if user has management rights on the BW or is an admin.

    Args:
        user: The User to check
        bw: The BusinessWall instance

    Returns:
        True if user is a manager of the BW or has admin role
    """
    if user.has_role(RoleEnum.ADMIN):
        return True
    return user.id in bw_managers_ids(bw)


#: The activation funnel's session state, at the value each key takes
#: before anything has been chosen. The three writers below used to
#: spell these seven names out one `session[...] = ...` at a time, 21
#: string literals in all, where a typo was silent.
_INITIAL_STATE: dict[str, Any] = {
    "bw_type": None,
    "bw_type_confirmed": False,
    "suggested_bw_type": "media",  # Default suggestion based on KYC
    "contacts_confirmed": False,
    "bw_activated": False,
    "pricing_value": None,
}

#: The same state once a BW has been in play and is being dropped: no
#: id, and no suggestion either — the KYC default would be misleading
#: after an explicit cancellation.
_CLEARED_STATE: dict[str, Any] = _INITIAL_STATE | {
    "bw_id": None,
    "suggested_bw_type": "",
    "error": "",
}


def init_session():
    """Initialize session with default values if not set.

    This function sets up all necessary session variables for the
    Business Wall activation workflow.
    """
    for key, value in _INITIAL_STATE.items():
        session.setdefault(key, value)


def fill_session(current_bw: BusinessWall) -> None:
    """Load into session information from current Businesswall."""
    session.update(
        _CLEARED_STATE
        | {
            "bw_id": str(current_bw.id),
            "bw_type": current_bw.bw_type,
            "bw_type_confirmed": True,
            "suggested_bw_type": current_bw.bw_type,
            "contacts_confirmed": True,
            "bw_activated": True,
        }
    )
    _remember_selected_bw(current_bw.id)


def clear_bw_session() -> None:
    """Clear session BW information when cancelling subscription."""
    session.update(_CLEARED_STATE)
    _remember_selected_bw(None)


def _remember_selected_bw(bw_id: UUID | None) -> None:
    """Persist the signed-in user's BW choice across sessions.

    `contextlib.suppress(Exception)` used to wrap this, so a failed
    commit was invisible *and* left the session needing a rollback —
    the next statement of the same request then died with a
    `PendingRollbackError` pointing nowhere near the cause. The write
    stays best-effort: the session already carries the choice for this
    request, and losing the cross-session memory is not worth failing
    the page over. But it says so out loud and hands back a usable
    session.
    """
    user = g.user
    if not user or user.is_anonymous:
        return
    user.selected_bw_id = bw_id
    try:
        db.session.commit()
    except SQLAlchemyError as e:
        db.session.rollback()
        warn(f"Could not persist selected_bw_id={bw_id} for user {user.id}: {e}")


def init_missions_state():
    """Initialize missions state in session if not present.

    Sets all mission permissions to False by default.
    """
    if "missions" not in session:
        session["missions"] = {
            PermissionType.PRESS_RELEASE.value: False,
            PermissionType.EVENTS.value: False,
            PermissionType.MISSIONS.value: False,
            PermissionType.PROJECTS.value: False,
            PermissionType.INTERNSHIPS.value: False,
            PermissionType.APPRENTICESHIPS.value: False,
            PermissionType.DOCTORAL.value: False,
        }


# Roles that grant access to the Business Wall management dashboard.
# Centralised so the predicate stays in sync between the dashboard
# route guard and any UI surface that links to it (bug #0139).
#
# BWPRi and BWPRe are intentionally NOT in this set: PR managers can
# publish on behalf of the BW (handled by partnership-aware authorization
# in user_utils) but do not reach the management dashboard — clicking
# "Aller au tableau de bord" used to land them on a 403 (#0139), and an
# owner whose only accepted role was BWPRi could manage a BW they had no
# business managing (#0157). Both are guarded by regression tests; do
# not add BWPRi/BWPRe here without updating those tests first.
DASHBOARD_ACCESS_ROLES: frozenset[str] = frozenset(
    {
        BWRoleType.BW_OWNER.value,
        BWRoleType.BWMI.value,
        BWRoleType.BWME.value,
    }
)


def can_access_bw_dashboard(role_type: str) -> bool:
    """True if `role_type` grants access to the BW management dashboard.

    Bug #0139: the role list was previously inlined in
    `confirm_role_invitation.py` and risked drifting from the dashboard
    route guard. Lifted here so both call sites consult the same source.
    """
    return role_type in DASHBOARD_ACCESS_ROLES


def bw_managers_ids(bw: BusinessWall) -> set[int]:
    """Get the set of user IDs with management rights (BWMI, BWME, BW_OWNER) on the BusinessWall.
    Args:
        bw: A BusinessWall instance

    Returns:
        Set of user IDs with management role
    """
    required_status = {InvitationStatus.ACCEPTED.value}
    manager_ids = bw_roles_ids(bw, set(DASHBOARD_ACCESS_ROLES), required_status)
    # Bug #0157: the owner used to be added *unconditionally* "for the
    # first stage of BW registration". But that let an owner whose only
    # accepted role is BWPRi (PR Manager — not a dashboard role) reach
    # the BW management dashboard. The fallback is only a bootstrap
    # safety net: keep it solely while no accepted dashboard manager
    # exists yet. Once a real manager (BW_OWNER / BWMi / BWMe) is in
    # place, dashboard access requires an accepted management role.
    if not manager_ids:
        manager_ids.add(bw.owner_id)
    return manager_ids


def bw_pr_managers_ids(bw: BusinessWall) -> set[int]:
    """Get the set of user IDs with PR management rights
    (BWPRI, BWPRE, BW_OWNER) on the BusinessWall.

    Args:
        bw: A BusinessWall instance

    Returns:
        Set of user IDs with PR management role
    """
    required_roles = {
        BWRoleType.BW_OWNER.value,
        BWRoleType.BWPRI.value,
        BWRoleType.BWPRE.value,
    }
    required_status = {InvitationStatus.ACCEPTED.value}
    manager_ids = bw_roles_ids(bw, required_roles, required_status)
    manager_ids.add(bw.owner_id)
    return manager_ids


def bw_roles_ids(
    bw: BusinessWall, required_roles: set[str], required_status: set[str]
) -> set[int]:
    """Get the set of user IDs with management rights of given type on the BusinessWall.

    Args:
        bw: A BusinessWall instance
        required_roles: set of BWRoleType values
        required_status: set of InvitationStatus values

    Returns:
        Set of user IDs with management role
    """

    manager_ids: set[int] = set()
    if bw.role_assignments:
        for assignment in bw.role_assignments:
            if (
                assignment.invitation_status in required_status
                and assignment.role_type in required_roles
            ):
                manager_ids.add(assignment.user_id)

    return manager_ids


def get_press_relation_bw_list() -> list[BusinessWall]:
    """Return the list of active PR BusinessWall instances"""

    bw_service = container.get(BusinessWallService)
    return cast(
        list[BusinessWall],
        bw_service.list(
            bw_type=BWType.PR.value,
            status=BWStatus.ACTIVE.value,
        ),
    )


def _get_press_relation_bw_list_for_status(
    businesswall: BusinessWall,
    partnership_status: set[str],
    *,
    service: BusinessWallService | None = None,
) -> list[tuple[BusinessWall, str]]:
    """Returns the list of PR BW partners of the given BusinessWall for given status.

    Args:
        businesswall: The BusinessWall whose partnerships are inspected.
        partnership_status: Set of `Partnership.status` values to keep.
        service: Optional `BusinessWallService` used to resolve partner BW
            ids. Defaults to the container-resolved production service.
            Injected for tests (Pattern B — DI via default-arg).
    """

    bw_service = service if service is not None else container.get(BusinessWallService)

    result: list[tuple[BusinessWall, str]] = []
    for partnership in businesswall.partnerships or []:
        if partnership.status in partnership_status and partnership.partner_bw_id:
            partner_bw = bw_service.get(UUID(partnership.partner_bw_id))
            if partner_bw:
                result.append((partner_bw, partnership.status))

    return result


def get_current_press_relation_bw_list(
    businesswall: BusinessWall,
    *,
    service: BusinessWallService | None = None,
) -> list[BusinessWall]:
    """Returns the list of active PR BW partners of the given BusinessWall."""

    return [
        bw_status[0]
        for bw_status in _get_press_relation_bw_list_for_status(
            businesswall, {PartnershipStatus.ACTIVE.value}, service=service
        )
    ]


def get_pending_press_relation_bw_list(
    businesswall: BusinessWall,
    *,
    service: BusinessWallService | None = None,
) -> list[tuple[BusinessWall, str]]:
    """Returns the list of pending and status PR BW partners of the given BusinessWall."""

    return _get_press_relation_bw_list_for_status(
        businesswall,
        {
            PartnershipStatus.INVITED.value,
            PartnershipStatus.REJECTED,
            PartnershipStatus.EXPIRED,
        },
        service=service,
    )


def get_invited_press_relation_bw_list(
    businesswall: BusinessWall,
    *,
    service: BusinessWallService | None = None,
) -> list[BusinessWall]:
    """Returns the list of PR BW partners with invited status for given BusinessWall."""
    return [
        bw_status[0]
        for bw_status in _get_press_relation_bw_list_for_status(
            businesswall, {PartnershipStatus.INVITED.value}, service=service
        )
    ]


def bw_contact_name_email(bw: BusinessWall, *, loader=None) -> tuple[str, str]:
    """Returns the contact name and email of the Business Wall owner.

    Args:
        bw: The BusinessWall instance whose owner contact to fetch.
        loader: Optional ``(owner_id) -> User`` callable for testing /
            DI. Defaults to fetching the user from ``db.session`` via
            :func:`get_obj`.
    """
    if loader is None:
        owner = cast(User, get_obj(bw.owner_id, User))
    else:
        owner = loader(bw.owner_id)
    return owner.full_name, owner.email


# Translation map for partnership status as shown to humans in the
# pending PR BW dashboard. Lifted to module scope so the pure
# `_pending_bw_to_info_dict` helper can be unit-tested without rebuilding
# the dict on every call.
_PENDING_STATUS_TRANSLATION: dict[str, str] = {
    "invited": "invitation en cours",
    "rejected": "invitation rejetée",
    "expired": "invitation expirée",
}


def _pending_bw_to_info_dict(
    bw: BusinessWall,
    status: str,
    contact: tuple[str, str],
) -> dict[str, str]:
    """Pure helper: build the pending-PR-BW info dict.

    Extracted from `get_pending_pr_bw_info_list` so the dict-shape
    contract (key set, status translation, contact passthrough) can be
    unit-tested without any DB access.

    Args:
        bw: The partner BusinessWall whose name appears in the row.
        status: Raw partnership status string ("invited" / "rejected" /
            "expired"). Unknown values fall back to the raw status.
        contact: ``(contact_name, contact_email)`` tuple, already
            resolved by the caller via ``bw_contact_name_email``.

    Returns:
        Dict with keys ``bw_name``, ``bw_contact_name``,
        ``bw_contact_email``, ``bw_status``.
    """
    return {
        "bw_name": bw.name_safe,
        "bw_contact_name": contact[0],
        "bw_contact_email": contact[1],
        "bw_status": _PENDING_STATUS_TRANSLATION.get(status, status),
    }


def _current_bw_to_info_dict(
    bw: BusinessWall,
    contact: tuple[str, str],
) -> dict[str, str]:
    """Pure helper: build the active-PR-BW info dict.

    Extracted from `get_current_pr_bw_info_list` so the dict-shape
    contract (key set, id stringification, contact passthrough) can be
    unit-tested without any DB access.

    Args:
        bw: The partner BusinessWall.
        contact: ``(contact_name, contact_email)`` tuple, already
            resolved by the caller via ``bw_contact_name_email``.

    Returns:
        Dict with keys ``bw_name``, ``bw_contact_name``,
        ``bw_contact_email``, ``bw_id`` (always stringified).
    """
    return {
        "bw_name": bw.name_safe,
        "bw_contact_name": contact[0],
        "bw_contact_email": contact[1],
        "bw_id": str(bw.id),
    }


def get_pending_pr_bw_info_list(businesswall: BusinessWall) -> list[dict[str, str]]:
    """Returns list of pending PR Business Walls with their info."""
    pending_bw_status_list = get_pending_press_relation_bw_list(businesswall)
    return [
        _pending_bw_to_info_dict(bw, status, bw_contact_name_email(bw))
        for bw, status in pending_bw_status_list
    ]


def get_current_pr_bw_info_list(businesswall: BusinessWall) -> list[dict[str, str]]:
    """Returns list of active PR BW with their info."""
    current_bw_list = get_current_press_relation_bw_list(businesswall)
    return [
        _current_bw_to_info_dict(bw, bw_contact_name_email(bw))
        for bw in current_bw_list
    ]
