# Copyright (c) 2025, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Route modules for Business Wall activation workflow.

This package organizes routes by workflow stage for better maintainability.
Importing this package registers all routes on the blueprint via side effects.
"""

from __future__ import annotations

# Import all route modules - this registers routes on the blueprint
from . import dashboard, stage1, stage2, stage3, stage4, stage5, stage6, stage7

__all__ = [
    "dashboard",
    "stage1",
    "stage2",
    "stage3",
    "stage4",
    "stage5",
    "stage6",
    "stage7",
]
