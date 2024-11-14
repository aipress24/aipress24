# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from flask import Blueprint

blueprint = Blueprint(
    "kyc",
    __name__,
    url_prefix="/kyc",
    template_folder="templates",
    static_folder="static",
)
route = blueprint.route
get = blueprint.get
post = blueprint.post

# @blueprint.before_request
# def check_auth():
#     user = cast(User, current_user)
#     if user.is_anonymous:
#         raise Unauthorized
