# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from flask_sqlalchemy import SQLAlchemy

from app.services.zip_codes import create_country_entry, get_country
from app.services.zip_codes._country_service import (
    check_countries_exist,
    get_countries,
    get_full_countries,
    update_country_entry,
)


class TestGetCountry:
    """Test suite for get_country function."""

    def test_returns_country_name(self, db: SQLAlchemy) -> None:
        """Test get_country returns country name for valid iso3."""
        create_country_entry("FRA", "France")
        db.session.flush()

        country = get_country("FRA")

        assert country == "France"

    def test_returns_empty_for_unknown_iso3(self, db: SQLAlchemy) -> None:
        """Test get_country returns empty string for unknown iso3."""
        country = get_country("XXX")

        assert country == ""


class TestCheckCountriesExist:
    """Test suite for check_countries_exist function."""

    def test_returns_false_when_no_countries(self, db: SQLAlchemy) -> None:
        """Test returns False when countries table is empty."""
        result = check_countries_exist()

        assert result is False

    def test_returns_true_when_countries_exist(self, db: SQLAlchemy) -> None:
        """Test returns True when countries exist."""
        create_country_entry("USA", "United States")
        db.session.flush()

        result = check_countries_exist()

        assert result is True


class TestGetCountries:
    """Test suite for get_countries function."""

    def test_returns_empty_list_when_no_countries(self, db: SQLAlchemy) -> None:
        """Test returns empty list when no countries."""
        result = get_countries()

        assert result == []

    def test_returns_list_of_country_names(self, db: SQLAlchemy) -> None:
        """Test returns list of country names."""
        create_country_entry("FRA", "France")
        create_country_entry("DEU", "Germany")
        db.session.flush()

        result = get_countries()

        assert "France" in result
        assert "Germany" in result

    def test_returns_sorted_by_name(self, db: SQLAlchemy) -> None:
        """Test returns countries sorted by name."""
        create_country_entry("DEU", "Germany")
        create_country_entry("FRA", "France")
        create_country_entry("BEL", "Belgium")
        db.session.flush()

        result = get_countries()

        assert result == ["Belgium", "France", "Germany"]


class TestGetFullCountries:
    """Test suite for get_full_countries function."""

    def test_returns_empty_list_when_no_countries(self, db: SQLAlchemy) -> None:
        """Test returns empty list when no countries."""
        result = get_full_countries()

        assert result == []

    def test_returns_list_of_tuples(self, db: SQLAlchemy) -> None:
        """Test returns list of (iso3, name) tuples."""
        create_country_entry("FRA", "France", seq=1)
        db.session.flush()

        result = get_full_countries()

        assert ("FRA", "France") in result

    def test_returns_sorted_by_seq(self, db: SQLAlchemy) -> None:
        """Test returns countries sorted by seq."""
        create_country_entry("DEU", "Germany", seq=2)
        create_country_entry("FRA", "France", seq=1)
        create_country_entry("BEL", "Belgium", seq=3)
        db.session.flush()

        result = get_full_countries()

        assert result[0] == ("FRA", "France")
        assert result[1] == ("DEU", "Germany")
        assert result[2] == ("BEL", "Belgium")


class TestUpdateCountryEntry:
    """Test suite for update_country_entry function."""

    def test_creates_entry_if_not_exists(self, db: SQLAlchemy) -> None:
        """Test creates new entry if iso3 doesn't exist."""
        result = update_country_entry("ESP", "Spain", seq=10)
        db.session.flush()

        assert result is True
        assert get_country("ESP") == "Spain"

    def test_returns_false_if_no_changes(self, db: SQLAlchemy) -> None:
        """Test returns False if entry exists with same values."""
        create_country_entry("ITA", "Italy", seq=5)
        db.session.flush()

        result = update_country_entry("ITA", "Italy", seq=5)

        assert result is False

    def test_updates_existing_entry(self, db: SQLAlchemy) -> None:
        """Test updates existing entry with new values."""
        create_country_entry("GBR", "United Kingdom", seq=1)
        db.session.flush()

        result = update_country_entry("GBR", "United Kingdom", seq=99)
        db.session.flush()

        assert result is True


class TestCreateCountryEntry:
    """Test suite for create_country_entry function."""

    def test_creates_country_with_defaults(self, db: SQLAlchemy) -> None:
        """Test creates country with default seq=0."""
        create_country_entry("NLD", "Netherlands")
        db.session.flush()

        assert get_country("NLD") == "Netherlands"

    def test_creates_country_with_seq(self, db: SQLAlchemy) -> None:
        """Test creates country with specified seq."""
        create_country_entry("PRT", "Portugal", seq=15)
        db.session.flush()

        result = get_full_countries()
        assert ("PRT", "Portugal") in result
