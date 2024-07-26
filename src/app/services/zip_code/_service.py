# Copyright (c) 2021-2024 - Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from sqlalchemy import select

from app.flask.extensions import db

from ._models import ZipCodeEntry


def get_zip_code_country(iso3: str) -> list[dict[str, str]]:
    """Get list of vlue/label for a country."""
    query = (
        select(ZipCodeEntry)
        .where(ZipCodeEntry.iso3 == iso3)
        .order_by(ZipCodeEntry.zip_code)
    )
    results = db.session.scalars(query).all()
    return [{"value": row.value, "label": row.label} for row in results]


# no qa : Too many arguments in function definition (6 > 5)
def create_zip_code_entry(
    iso3: str,
    zip_code: str,
    name: str,
    value: str,
    label: str,
) -> None:
    """Create a new entry in the zip_code table."""
    entry = ZipCodeEntry(
        iso3=iso3,
        zip_code=zip_code,
        name=name,
        value=value,
        label=label,
    )
    db.session.add(entry)
