# Copyright (c) 2021-2024 - Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from flask import Blueprint

blueprint = Blueprint(
    "wallet", __name__, url_prefix="/wallet", template_folder="templates"
)
route = blueprint.route

# @blueprint.before_request
# def check_admin():
#     user = cast(User, current_user)
#     if not has_role(user, "admin"):
#         raise Unauthorized
