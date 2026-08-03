# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Unit tests for app.flask.bootstrap.zip_codes."""

from __future__ import annotations

from sqlalchemy import select

from app.flask.bootstrap.zip_codes import (
    import_default_zip_code_for_country,
)
from app.services.zip_codes import ZipCodeEntry


def test_import_default_zip_code_for_country(db) -> None:
    iso3 = "XYZ"
    msg = "Aucune information sur les codes postaux"
    import_default_zip_code_for_country(iso3)
    db.session.flush()

    entries = list(
        db.session.scalars(select(ZipCodeEntry).where(ZipCodeEntry.iso3 == iso3)).all()
    )
    assert len(entries) == 1
    entry = entries[0]
    assert entry.iso3 == "XYZ"
    assert entry.zip_code == "000"
    assert entry.name == msg
    assert entry.value == f"XYZ / 000 {msg}"
    assert entry.label == f"000 {msg}"
