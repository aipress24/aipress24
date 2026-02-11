# Copyright (c) 2025, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Utility functions for Business Wall activation workflow."""

from __future__ import annotations

from flask import session


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


def get_mock_owner_data() -> dict[str, str]:
    """Get mock owner data for pre-filling forms.

    In production, this would fetch data from the current_user object.

    Returns:
        Dictionary containing owner contact information.
    """
    return {
        "first_name": "Alice",
        "last_name": "Dupont",
        "email": "alice.dupont@example.com",
        "phone": "+33 1 23 45 67 89",
    }


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
