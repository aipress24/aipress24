# Copyright (c) 2021-2024 - Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from flask import jsonify
from flask_login import current_user

from app.services.healthcheck import healthcheck
from app.typing import JsonDict

from .. import blueprint


@blueprint.route("/health")
def health() -> str:
    healthcheck()
    return "Healthy: OK"


@blueprint.route("/test")
def test():
    """This endpoint will be used by tests."""
    user = current_user
    result: JsonDict = {}
    if user.is_anonymous:
        result["user"] = {}
    else:
        result["user"] = {
            "id": user.id,
            # "username": user.username,
            "email": user.email,
        }
    return jsonify(**result)
