# Copyright (c) 2025, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Utility functions for Business Wall activation workflow."""

from __future__ import annotations

from typing import cast

from flask import session
from svcs.flask import container

from app.flask.sqla import get_obj
from app.models.auth import User
from app.modules.bw.bw_activation.models import (
    BusinessWall,
    BusinessWallService,
    BWRoleType,
    BWStatus,
    BWType,
    InvitationStatus,
    PartnershipStatus,
)

# from app.modules.bw.bw_activation.models.repositories import BusinessWallRepository

ERR_NOT_MANAGER = (
    "Votre identification ne semble pas permettre la gestion de ce Business Wall."
)
ERR_BW_NOT_FOUND = "Aucun Business Wall trouvé."
ERR_NO_ORGANISATION = "Aucun Organisation trouvée pour le Business Wall."
ERR_UNKNOWN_ACTION = "Erreur interne, action inconnue."
ERR_WRONG_VALIDATION_LINK = "Lien de validation erroné."
ERR_INVITATION_NOT_FOUND = "Invitation non trouvée."


def init_session():
    """Initialize session with default values if not set.

    This function sets up all necessary session variables for the
    Business Wall activation workflow.
    """
    if "bw_type" not in session:
        session["bw_type"] = None
    if "bw_type_confirmed" not in session:
        session["bw_type_confirmed"] = False
    if "suggested_bw_type" not in session:
        session["suggested_bw_type"] = "media"  # Default suggestion based on KYC
    if "contacts_confirmed" not in session:
        session["contacts_confirmed"] = False
    if "bw_activated" not in session:
        session["bw_activated"] = False
    if "pricing_value" not in session:
        session["pricing_value"] = None


def fill_session(current_bw: BusinessWall) -> None:
    """Load into session information from current Businesswall."""
    session["bw_type"] = current_bw.bw_type
    session["bw_type_confirmed"] = True
    session["suggested_bw_type"] = current_bw.bw_type
    session["contacts_confirmed"] = True
    session["bw_activated"] = True
    session["pricing_value"] = None
    session["error"] = ""


def init_missions_state():
    """Initialize missions state in session if not present.

    Sets all mission permissions to False by default.
    """
    if "missions" not in session:
        session["missions"] = {
            "press_release": False,
            "events": False,
            "missions": False,
            "projects": False,
            "internships": False,
            "apprenticeships": False,
            "doctoral": False,
        }


def bw_managers_ids(bw: BusinessWall) -> set[int]:
    """Get the set of user IDs with management rights (BWMI, BWME, BW_OWNER) on the BusinessWall.
    Args:
        bw: A BusinessWall instance

    Returns:
        Set of user IDs with management role
    """
    required_roles = {
        BWRoleType.BW_OWNER.value,
        BWRoleType.BWMI.value,
        BWRoleType.BWME.value,
    }
    required_status = {InvitationStatus.ACCEPTED.value}
    manager_ids = bw_roles_ids(bw, required_roles, required_status)
    manager_ids.add(bw.owner_id)  # usefull in first stage of BW registration
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


def get_current_press_relation_bw_list(bw: BusinessWall) -> list[BusinessWall]:
    """Returns the list of active PR BW partners of the given BusinessWall."""
    from uuid import UUID

    bw_service = container.get(BusinessWallService)

    active_partnerships = [
        partner
        for partner in (bw.partnerships or [])
        if partner.status == PartnershipStatus.ACTIVE.value
    ]

    result: list[BusinessWall] = []
    for partnership in active_partnerships:
        # partner_bw_id is the UUID of the partner BusinessWall
        if partnership.partner_bw_id:
            partner_bw = bw_service.get(UUID(partnership.partner_bw_id))
            if partner_bw:
                result.append(partner_bw)

    return result


def get_pending_press_relation_bw_list(bw: BusinessWall) -> list[BusinessWall]:
    """Returns the list of pending PR BW partners of the given BusinessWall."""
    from uuid import UUID

    bw_service = container.get(BusinessWallService)

    active_partnerships = [
        partner
        for partner in (bw.partnerships or [])
        if partner.status != PartnershipStatus.ACTIVE.value
    ]

    result: list[BusinessWall] = []
    for partnership in active_partnerships:
        # partner_bw_id is the UUID of the partner BusinessWall
        if partnership.partner_bw_id:
            partner_bw = bw_service.get(UUID(partnership.partner_bw_id))
            if partner_bw:
                result.append(partner_bw)

    return result


def bw_contact_name_email(bw: BusinessWall) -> tuple[str, str]:
    """Returns the contact name and email of the Business Wall owner."""
    owner = cast(User, get_obj(bw.owner_id, User))
    return owner.full_name, owner.email


def get_pending_pr_bw_info_list(businesswall: BusinessWall) -> list[dict[str, str]]:
    """Returns list of pending PR Business Walls with their info."""
    pending_bw_list = get_pending_press_relation_bw_list(businesswall)
    result: list[dict[str, str]] = {}
    for bw in pending_bw_list:
        info = bw_contact_name_email(bw)
        result.append(
            {
                "bw_name": bw.name_safe,
                "bw_contact_name": info[0],
                "bw_contact_email": info[1],
            }
        )
