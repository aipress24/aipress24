# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

import sys

from sqlalchemy import Sequence, select

from app.flask.extensions import db

from ._models import ZipCodeEntry


def check_zip_code_exist(iso3: str) -> bool:
    """Return existence of any row in the zip_code table"""
    return (
        db.session.query(ZipCodeEntry).filter(ZipCodeEntry.iso3 == iso3).first()
        is not None
    )


def _select_all(iso3: str) -> Sequence[ZipCodeEntry]:
    """Get list of all rows for a country."""
    query = (
        select(ZipCodeEntry)
        .where(ZipCodeEntry.iso3 == iso3)
        .order_by(ZipCodeEntry.zip_code, ZipCodeEntry.name)
    )
    return db.session.scalars(query).all()


def get_zip_code_country(iso3: str) -> list[dict[str, str]]:
    """Get list of value/label for a country."""
    return [{"value": row.value, "label": row.label} for row in _select_all(iso3)]


def get_full_zip_code_country(iso3: str) -> list[tuple[str, str, str, str]]:
    """Get list of aip_code/name/value/label for a country."""
    return [(row.zip_code, row.name, row.value, row.label) for row in _select_all(iso3)]


def update_zip_code_entry(
    iso3: str,
    zip_code: str,
    name: str,
    value: str,
    label: str,
) -> bool:
    """Update an entry if necessary."""
    query = select(ZipCodeEntry).filter(ZipCodeEntry.value == value)
    result = db.session.execute(query).scalar()
    if not result:
        create_zip_code_entry(iso3, zip_code, name, value, label)
        return True

    if (
        result.iso3 == iso3
        and result.zip_code == zip_code
        and result.name == name
        and result.label == label
    ):
        # unchanged item
        # print("/////////////////// no change", file=sys.stderr)
        return False

    # update required
    print(
        f"    update: {result.iso3}, {result.zip_code}, {result.name} ->  {iso3}, {zip_code}, {name}",
        file=sys.stderr,
    )

    result.iso3 = iso3
    result.zip_code = zip_code
    result.name = name
    result.label = label

    return True


def create_zip_code_entry(
    iso3: str, zip_code: str, name: str, value: str, label: str
) -> None:
    """Create a new entry in the zip_code table."""
    entry = ZipCodeEntry(
        iso3=iso3, zip_code=zip_code, name=name, value=value, label=label
    )
    db.session.add(entry)
