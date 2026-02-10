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

from flask import Blueprint

# Create the blueprint
bp = Blueprint("bw_activation_full", __name__, template_folder="../../templates")

# Import routes - this registers all routes via side effects
from . import routes  # noqa: E402, F401

# Export the blueprint
__all__ = ["bp"]
