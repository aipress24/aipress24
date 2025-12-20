# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Admin views using Flask routes with @nav() decorator."""

from __future__ import annotations

# Import all view modules to register routes
from . import (
    _export,
    contents,
    db_export,
    exports,
    groups,
    home,
    orgs,
    promotions,
    show_org,
    show_user,
    system,
    users,
    validation,
)

__all__ = [
    "_export",
    "contents",
    "db_export",
    "exports",
    "groups",
    "home",
    "orgs",
    "promotions",
    "show_org",
    "show_user",
    "system",
    "users",
    "validation",
]
