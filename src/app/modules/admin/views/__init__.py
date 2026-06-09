# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Admin views using Flask routes with @nav() decorator."""

from __future__ import annotations

# Import all view modules to register routes
from . import (
    _export,
    biz_moderation,
    cms,
    contents,
    db_export,
    debug_purchase,
    dramatiq_dashboard,
    exports,
    groups,
    home,
    orgs,
    promotions,
    sales_recap,
    show_org,
    show_user,
    stripe_products,
    system,
    users,
    validation,
)

__all__ = [
    "_export",
    "biz_moderation",
    "cms",
    "contents",
    "db_export",
    "debug_purchase",
    "dramatiq_dashboard",
    "exports",
    "groups",
    "home",
    "orgs",
    "promotions",
    "sales_recap",
    "show_org",
    "show_user",
    "stripe_products",
    "system",
    "users",
    "validation",
]
