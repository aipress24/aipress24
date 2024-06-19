# Copyright (c) 2021-2024 - Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from flask import Blueprint

blueprint = Blueprint("public", __name__, url_prefix="", template_folder="templates")
route = blueprint.route
