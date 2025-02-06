# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from sqlalchemy import select

from app.flask.extensions import db

from ._models import CountryEntry


def check_countries_exist() -> bool:
    """Return existence of any row in the countries table"""
    return db.session.query(CountryEntry).first() is not None


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


def get_full_countries() -> list[tuple[str, str]]:
    """Get list of countries (code and name) from the database."""
    query = select(CountryEntry).order_by(CountryEntry.seq)
    results = db.session.scalars(query).all()
    return [(row.iso3, row.name) for row in results]


def update_country_entry(iso3: str, name: str, seq: int = 0) -> bool:
    """Update an entry if necessary."""
    query = select(CountryEntry).filter(CountryEntry.iso3 == iso3)
    result = db.session.execute(query).scalar()

    if not result:
        create_country_entry(iso3, name, seq)
        return True

    if result.iso3 == iso3 and result.name == name and result.seq == seq:
        return False

    result.iso3 = iso3
    result.name = name
    result.seq = seq

    return True


def create_country_entry(iso3: str, name: str, seq: int = 0) -> None:
    """Create a new entry in the country table."""
    entry = CountryEntry(iso3=iso3, name=name, seq=seq)
    db.session.add(entry)
