# Copyright (c) 2025, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Utility functions for Business Wall activation workflow."""

from __future__ import annotations

from flask import session

from app.modules.bw.bw_activation.models import BusinessWall, InvitationStatus

# from app.modules.bw.bw_activation.models.repositories import BusinessWallRepository


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
    """Get the set of user IDs with management rights on the BusinessWall.

    Args:
        bw: A BusinessWall instance

    Returns:
        Set of user IDs with management rights
    """

    manager_ids: set[int] = set()

    manager_ids.add(bw.owner_id)
    if bw.role_assignments:
        for assignment in bw.role_assignments:
            if assignment.invitation_status == InvitationStatus.ACCEPTED.value:
                manager_ids.add(assignment.user_id)

    return manager_ids
