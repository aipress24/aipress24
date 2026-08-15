# Copyright (c) 2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Loading countries and zip codes must never destroy what it can't replace.

Bugs #0287 / #0288 : « le champ Pays ne se remplit pas », then « la table
des pays est actuellement cassée ». The loader deleted the countries and
committed before reading its source file, and caught the read failure —
so one bad run emptied the table for good, silently, and the admin page
still reported success.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest
from sqlalchemy import select

from app.flask.bootstrap.zip_codes import (
    DEFAULT_NO_ZIP_CODE,
    import_countries,
    import_zip_codes,
)
from app.services.zip_codes import CountryEntry, ZipCodeEntry

if TYPE_CHECKING:
    from pathlib import Path

COUNTRIES = [
    {"iso3": "DEU", "name": "Allemagne"},
    {"iso3": "FRA", "name": "France"},
]


def write_countries(tmp_path: Path, countries: list[dict] | None = None) -> Path:
    path = tmp_path / "pays.json"
    path.write_text(json.dumps(COUNTRIES if countries is None else countries))
    return path


def country_names(db) -> list[str]:
    return list(
        db.session.scalars(select(CountryEntry.name).order_by(CountryEntry.seq)).all()
    )


class TestImportCountries:
    def test_replaces_the_table(self, db, tmp_path: Path) -> None:
        db.session.add(CountryEntry(iso3="XXX", name="Ancien pays", seq=0))
        db.session.commit()

        import_countries(write_countries(tmp_path))

        # France first, then alphabetical by iso3 — the order the KYC
        # country selector relies on.
        assert country_names(db) == ["France", "Allemagne"]

    def test_missing_file_leaves_the_table_alone(self, db, tmp_path: Path) -> None:
        """The regression itself: no source, no destruction."""
        import_countries(write_countries(tmp_path))

        with pytest.raises(FileNotFoundError):
            import_countries(tmp_path / "does-not-exist.json")

        assert country_names(db) == ["France", "Allemagne"]

    def test_unreadable_file_leaves_the_table_alone(self, db, tmp_path: Path) -> None:
        """Erick's actual case: the file was there, its contents weren't."""
        import_countries(write_countries(tmp_path))

        broken = tmp_path / "broken.json"
        broken.write_text("{ this is not json")
        with pytest.raises(json.JSONDecodeError):
            import_countries(broken)

        assert country_names(db) == ["France", "Allemagne"]


class TestImportZipCodes:
    def test_country_without_a_towns_file_gets_a_placeholder(
        self, db, tmp_path: Path
    ) -> None:
        """Only 94 of the 216 countries ship a towns file.

        The loop used to call the placeholder loader with a bare iso3
        string where it expects a path, so it raised `AttributeError` on
        every one of them — and the bare `except` hid it. Those countries
        ended up with no zip code at all.
        """
        towns = tmp_path / "towns"
        towns.mkdir()

        import_zip_codes(write_countries(tmp_path), towns)

        entries = list(
            db.session.scalars(
                select(ZipCodeEntry).where(ZipCodeEntry.iso3 == "DEU")
            ).all()
        )
        assert len(entries) == 1
        assert entries[0].name == DEFAULT_NO_ZIP_CODE[0]["name"]

    def test_towns_file_is_loaded(self, db, tmp_path: Path) -> None:
        towns = tmp_path / "towns"
        towns.mkdir()
        (towns / "FRA.json").write_text(
            json.dumps([{"zip_code": "29200", "name": "Brest"}])
        )

        import_zip_codes(write_countries(tmp_path), towns)

        entry = db.session.scalars(
            select(ZipCodeEntry).where(ZipCodeEntry.iso3 == "FRA")
        ).one()
        assert entry.name == "Brest"
        assert entry.value == "FRA / 29200 Brest"

    def test_a_broken_country_file_is_reported_not_swallowed(
        self, db, tmp_path: Path
    ) -> None:
        """The other countries still load, but the run fails loudly and
        names the country that didn't."""
        towns = tmp_path / "towns"
        towns.mkdir()
        (towns / "FRA.json").write_text("{ not json")

        with pytest.raises(RuntimeError, match="FRA"):
            import_zip_codes(write_countries(tmp_path), towns)

        assert (
            db.session.scalars(
                select(ZipCodeEntry).where(ZipCodeEntry.iso3 == "DEU")
            ).first()
            is not None
        )
