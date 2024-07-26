# Copyright (c) 2021-2024 - Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from sqlalchemy import select

from app.flask.extensions import db

from ._models import CountryEntry


def get_country(iso3: str) -> str:
    """Get country from iso3 code."""
    query = select(CountryEntry).where(CountryEntry.iso3 == iso3)
    result = db.session.execute(query).first()
    if result:
        return result[0].name
    return ""


def get_countries() -> list[str]:
    """Get list of countries from the database."""
    query = select(CountryEntry).order_by(CountryEntry.name)
    result = db.session.execute(query).scalars()
    return [r.name for r in result]


def create_country_entry(
    iso3: str,
    name: str,
    seq: int = 0,
) -> None:
    """Create a new entry in the country table."""
    entry = CountryEntry(
        iso3=iso3,
        name=name,
        seq=seq,
    )
    db.session.add(entry)
