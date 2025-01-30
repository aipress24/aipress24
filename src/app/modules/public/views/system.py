# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from app.flask.cli.bootstrap import bootstrap
from app.flask.extensions import db
from app.services.zip_codes import ZipCodeRepository

from .. import get


@get("/bootstrap")
def bootstrap_view() -> str:
    zip_code_repo = ZipCodeRepository(session=db.session)
    count = zip_code_repo.count()
    if count:
        return "Bootstrap: Already done"

    bootstrap()
    return "Bootstrap: OK"
