# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

import operator
from importlib.metadata import distributions
from pathlib import Path
from typing import cast

from .base import BaseAdminPage
from .home import AdminHomePage


# Note: Route now handled by views_pages.py
class AdminSystemPage(BaseAdminPage):
    name = "system"
    label = "Système"
    title = "Système"

    template = "admin/pages/system.j2"
    icon = "server-cog"

    parent = AdminHomePage

    def context(self):
        sizes = []
        for distribution in distributions():
            size = 0
            files = distribution.files or []
            for file in files:
                path = cast(Path, file.locate())
                if not path.exists():
                    continue
                size += path.stat().st_size

            sizes += [(size, distribution)]

        sizes.sort(key=operator.itemgetter(0), reverse=True)

        packages_info = [("Size", "Name", "Version")]
        for size, distribution in sizes:
            name = distribution.metadata["Name"]
            version = distribution.metadata["Version"]
            size_str = f"{size / 1024 / 1024:.2f} MB"
            packages_info += [(size_str, name, version)]

        return {
            "packages": packages_info,
        }
