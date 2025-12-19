# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Admin views using Flask routes with @nav() decorator."""

from __future__ import annotations

# Import all view modules to register routes
from . import db_export, exports, home, orgs, promotions, system, users

__all__ = ["db_export", "exports", "home", "orgs", "promotions", "system", "users"]
