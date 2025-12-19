# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""
This is not used yet.
"""

from __future__ import annotations

from app.modules.admin.views._contents import (
    ContentsDataSource,
    ContentsTable,
    truncate,
)

from .base import AdminListPage


# Note: Route now handled by views/contents.py
class AdminContentsPage(AdminListPage):
    name = "contents"
    label = "Contenus"
    title = "Contenus"

    template = "admin/pages/generic_table.j2"
    icon = "rectangle-stack"

    ds_class = ContentsDataSource
    table_class = ContentsTable


__all__ = [
    "AdminContentsPage",
    "ContentsDataSource",
    "ContentsTable",
    "truncate",
]
