# Copyright (c) 2025, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Rights Sales Settings POC Blueprint.

Demonstrates the interface for configuring publication rights and licensing options.
"""

from __future__ import annotations

from flask import Blueprint, render_template

bp = Blueprint("rights_sales", __name__, template_folder="../templates")


@bp.route("/")
def index():
    """Display the rights sales settings interface."""
    return render_template("rights_sales.html")
