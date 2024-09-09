# Copyright (c) 2021-2024 - Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from app.flask.extensions import db
from app.models.unoff_orgs import UnoffOrganisation


def store_unoff_orga(name: str = "") -> bool:
    name = str(name).strip()
    if not name:
        return False
    db_session = db.session
    found_unoff_orga = db_session.get(UnoffOrganisation, name)
    if found_unoff_orga:
        return False
    db_session.add(UnoffOrganisation(name=name))
    db_session.commit()
    return True
