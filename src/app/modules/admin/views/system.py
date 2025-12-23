# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Admin system views."""

from __future__ import annotations

import operator
from importlib.metadata import distributions
from pathlib import Path
from typing import cast

from flask import render_template

from app.flask.lib.nav import nav
from app.modules.admin import blueprint


@blueprint.route("/system")
@nav(
    parent="index",
    icon="server-cog",
    label="Système",
)
def system():
    """System information page."""
    sizes = []
    for distribution in distributions():
        size = 0
        files = distribution.files or []
        for file in files:
            path = cast(Path, file.locate())
            if not path.exists():
                continue
            size += path.stat().st_size
        sizes.append((size, distribution))

    sizes.sort(key=operator.itemgetter(0), reverse=True)

    packages_info = [("Size", "Name", "Version")]
    for size, distribution in sizes:
        name = distribution.metadata["Name"]
        version = distribution.metadata["Version"]
        size_str = f"{size / 1024 / 1024:.2f} MB"
        packages_info.append((size_str, name, version))

    return render_template(
        "admin/pages/system.j2",
        title="Système",
        packages=packages_info,
    )
