# Copyright (c) 2025, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Business Wall Activation Full - Complete workflow with all BW types.

This blueprint demonstrates the complete Business Wall activation workflow:
- Free activation for 5 types (Media, Micro, Corporate Media, Union, Academics)
- Paid activation for 3 types (PR, Leaders & Experts, Transformers)
- Role assignment after activation
- Complete 7-stage management workflow

Package Structure:
    config.py - Business Wall types configuration
    utils.py - Utility functions and session management
    routes/ - Route handlers organized by workflow stage
        stage1.py - Subscription confirmation
        stage2.py - Contact nomination
        stage3.py - Activation (free/paid)
        stage4.py - Internal roles
        stage5.py - External partners
        stage6.py - Missions/permissions
        stage7.py - Content configuration
        dashboard.py - Dashboard and reset
"""

from __future__ import annotations

from flask import Blueprint, g, redirect, url_for

# Create the blueprint
bp = Blueprint("bw_activation", __name__, template_folder="./templates")


@bp.before_request
def require_login() -> None:
    """Check if the current user is allowed to activation pages."""
    user = g.user
    if not (user and user.is_authenticated):
        return redirect(url_for("security.login"))
    return None


# Import routes - this registers all routes via side effects
from . import (  # noqa: E402
    models,  # noqa: F401
    routes,  # noqa: E402, F401
)

# Export the blueprint
__all__ = ["bp"]
