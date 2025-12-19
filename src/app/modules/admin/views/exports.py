# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Admin exports views."""

from __future__ import annotations

from flask import render_template

from app.flask.lib.nav import nav
from app.modules.admin import blueprint


@blueprint.route("/exports")
@nav(parent="index", icon="file-down", label="Exports")
def exports():
    """Export page."""
    return render_template("admin/pages/exports.j2", title="Exports")
