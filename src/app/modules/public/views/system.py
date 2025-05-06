# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

import importlib.metadata

from flask import jsonify
from flask_login import current_user

from app.flask.cli.bootstrap import bootstrap
from app.flask.extensions import db
from app.modules.public import get
from app.services.healthcheck import healthcheck
from app.services.zip_codes import ZipCodeRepository
from app.typing import JsonDict


@get("/system/version/")
def version():
    return importlib.metadata.version("aipress24-flask")


@get("/system/boot")
def bootstrap_view() -> str:
    zip_code_repo = ZipCodeRepository(session=db.session)
    count = zip_code_repo.count()
    if count:
        return "Bootstrap: Already done"

    bootstrap()
    return "Bootstrap: OK"


@get("/system/health")
def health() -> str:
    healthcheck()
    return "Healthy: OK"


@get("/system/test")
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
