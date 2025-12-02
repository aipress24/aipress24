# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Tests for zip code service."""

from __future__ import annotations

from flask_sqlalchemy import SQLAlchemy

from app.services.zip_codes import (
    check_zip_code_exist,
    create_zip_code_entry,
    get_full_zip_code_country,
    get_zip_code_country,
    update_zip_code_entry,
)


class TestCheckZipCodeExist:
    """Test suite for check_zip_code_exist function."""

    def test_returns_false_when_no_entries(self, db: SQLAlchemy) -> None:
        """Should return False when no entries exist for country."""
        assert check_zip_code_exist("FRA") is False

    def test_returns_true_when_entries_exist(self, db: SQLAlchemy) -> None:
        """Should return True when entries exist for country."""
        create_zip_code_entry("FRA", "75018", "Paris", "75018", "Paris (75018)")
        db.session.flush()

        assert check_zip_code_exist("FRA") is True

    def test_returns_false_for_different_country(self, db: SQLAlchemy) -> None:
        """Should return False for country with no entries."""
        create_zip_code_entry("FRA", "75018", "Paris", "75018", "Paris (75018)")
        db.session.flush()

        assert check_zip_code_exist("USA") is False


class TestCreateZipCodeEntry:
    """Test suite for create_zip_code_entry function."""

    def test_creates_entry(self, db: SQLAlchemy) -> None:
        """Should create a new zip code entry."""
        create_zip_code_entry("FRA", "75001", "Paris 1er", "75001", "Paris 1er (75001)")
        db.session.flush()

        assert check_zip_code_exist("FRA") is True

    def test_creates_multiple_entries(self, db: SQLAlchemy) -> None:
        """Should create multiple entries for same country."""
        create_zip_code_entry("FRA", "75001", "Paris 1er", "75001", "Paris 1er")
        create_zip_code_entry("FRA", "75002", "Paris 2e", "75002", "Paris 2e")
        db.session.flush()

        entries = get_zip_code_country("FRA")
        assert len(entries) == 2


class TestGetZipCodeCountry:
    """Test suite for get_zip_code_country function."""

    def test_returns_empty_list_when_no_entries(self, db: SQLAlchemy) -> None:
        """Should return empty list when no entries exist."""
        result = get_zip_code_country("FRA")
        assert result == []

    def test_returns_value_label_pairs(self, db: SQLAlchemy) -> None:
        """Should return list of value/label dicts."""
        create_zip_code_entry("FRA", "75001", "Paris 1er", "val1", "Label 1")
        db.session.flush()

        result = get_zip_code_country("FRA")

        assert len(result) == 1
        assert result[0]["value"] == "val1"
        assert result[0]["label"] == "Label 1"

    def test_returns_sorted_by_zip_code(self, db: SQLAlchemy) -> None:
        """Should return entries sorted by zip code."""
        create_zip_code_entry("FRA", "75018", "Paris 18e", "val18", "Label 18")
        create_zip_code_entry("FRA", "75001", "Paris 1er", "val01", "Label 01")
        db.session.flush()

        result = get_zip_code_country("FRA")

        assert result[0]["value"] == "val01"
        assert result[1]["value"] == "val18"


class TestGetFullZipCodeCountry:
    """Test suite for get_full_zip_code_country function."""

    def test_returns_empty_list_when_no_entries(self, db: SQLAlchemy) -> None:
        """Should return empty list when no entries exist."""
        result = get_full_zip_code_country("FRA")
        assert result == []

    def test_returns_full_tuples(self, db: SQLAlchemy) -> None:
        """Should return list of (zip_code, name, value, label) tuples."""
        create_zip_code_entry("FRA", "75001", "Paris 1er", "val1", "Label 1")
        db.session.flush()

        result = get_full_zip_code_country("FRA")

        assert len(result) == 1
        assert result[0] == ("75001", "Paris 1er", "val1", "Label 1")


class TestUpdateZipCodeEntry:
    """Test suite for update_zip_code_entry function."""

    def test_creates_new_entry_if_not_exists(self, db: SQLAlchemy) -> None:
        """Should create entry if value doesn't exist."""
        result = update_zip_code_entry("FRA", "75001", "Paris", "val1", "Label 1")
        db.session.flush()

        assert result is True
        assert check_zip_code_exist("FRA") is True

    def test_returns_false_if_unchanged(self, db: SQLAlchemy) -> None:
        """Should return False if entry is unchanged."""
        create_zip_code_entry("FRA", "75001", "Paris", "val1", "Label 1")
        db.session.flush()

        result = update_zip_code_entry("FRA", "75001", "Paris", "val1", "Label 1")

        assert result is False

    def test_updates_existing_entry(self, db: SQLAlchemy) -> None:
        """Should update entry if different."""
        create_zip_code_entry("FRA", "75001", "Old Name", "val1", "Old Label")
        db.session.flush()

        result = update_zip_code_entry("FRA", "75001", "New Name", "val1", "New Label")
        db.session.flush()

        assert result is True

        # Verify update
        entries = get_full_zip_code_country("FRA")
        assert entries[0][1] == "New Name"
        assert entries[0][3] == "New Label"
