# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Tests for taxonomy service."""

from __future__ import annotations

from flask_sqlalchemy import SQLAlchemy

from app.services.taxonomies import (
    check_taxonomy_exists,
    create_entry,
    get_all_taxonomy_names,
    get_full_taxonomy,
    get_full_taxonomy_category_value,
    get_taxonomy,
    get_taxonomy_dual_select,
    update_entry,
)


class TestCheckTaxonomyExists:
    """Test suite for check_taxonomy_exists function."""

    def test_returns_false_when_no_taxonomy(self, db: SQLAlchemy) -> None:
        """Should return False when taxonomy doesn't exist."""
        assert check_taxonomy_exists("nonexistent") is False

    def test_returns_true_when_taxonomy_exists(self, db: SQLAlchemy) -> None:
        """Should return True when taxonomy exists."""
        create_entry("test_tax", "entry1")
        db.session.flush()

        assert check_taxonomy_exists("test_tax") is True


class TestCreateEntry:
    """Test suite for create_entry function."""

    def test_creates_basic_entry(self, db: SQLAlchemy) -> None:
        """Should create a basic taxonomy entry."""
        create_entry("test_tax", "Test Entry")
        db.session.flush()

        assert check_taxonomy_exists("test_tax") is True

    def test_creates_entry_with_all_fields(self, db: SQLAlchemy) -> None:
        """Should create entry with all optional fields."""
        create_entry("test_tax", "Test Entry", category="cat1", value="val1", seq=10)
        db.session.flush()

        result = get_full_taxonomy("test_tax")
        assert len(result) == 1
        assert result[0] == ("val1", "Test Entry")


class TestGetAllTaxonomyNames:
    """Test suite for get_all_taxonomy_names function."""

    def test_returns_empty_list_when_no_taxonomies(self, db: SQLAlchemy) -> None:
        """Should return empty list when no taxonomies exist."""
        result = get_all_taxonomy_names()
        assert result == []

    def test_returns_distinct_names(self, db: SQLAlchemy) -> None:
        """Should return distinct taxonomy names."""
        create_entry("tax_a", "entry1")
        create_entry("tax_a", "entry2")
        create_entry("tax_b", "entry1")
        db.session.flush()

        result = get_all_taxonomy_names()

        assert len(result) == 2
        assert "tax_a" in result
        assert "tax_b" in result

    def test_returns_sorted_names(self, db: SQLAlchemy) -> None:
        """Should return names in sorted order."""
        create_entry("tax_z", "entry1")
        create_entry("tax_a", "entry1")
        create_entry("tax_m", "entry1")
        db.session.flush()

        result = get_all_taxonomy_names()

        assert result == ["tax_a", "tax_m", "tax_z"]


class TestGetTaxonomy:
    """Test suite for get_taxonomy function."""

    def test_returns_empty_list_when_no_entries(self, db: SQLAlchemy) -> None:
        """Should return empty list for nonexistent taxonomy."""
        result = get_taxonomy("nonexistent")
        assert result == []

    def test_returns_entry_names(self, db: SQLAlchemy) -> None:
        """Should return list of entry names."""
        create_entry("test_tax", "Entry A")
        create_entry("test_tax", "Entry B")
        db.session.flush()

        result = get_taxonomy("test_tax")

        assert len(result) == 2
        assert "Entry A" in result
        assert "Entry B" in result

    def test_returns_sorted_by_name(self, db: SQLAlchemy) -> None:
        """Should return entries sorted by name."""
        create_entry("test_tax", "Zebra")
        create_entry("test_tax", "Apple")
        db.session.flush()

        result = get_taxonomy("test_tax")

        assert result == ["Apple", "Zebra"]


class TestGetFullTaxonomy:
    """Test suite for get_full_taxonomy function."""

    def test_returns_empty_list_when_no_entries(self, db: SQLAlchemy) -> None:
        """Should return empty list for nonexistent taxonomy."""
        result = get_full_taxonomy("nonexistent")
        assert result == []

    def test_returns_value_name_tuples(self, db: SQLAlchemy) -> None:
        """Should return list of (value, name) tuples."""
        create_entry("test_tax", "Test Name", value="test_val", seq=1)
        db.session.flush()

        result = get_full_taxonomy("test_tax")

        assert result == [("test_val", "Test Name")]

    def test_filters_by_category(self, db: SQLAlchemy) -> None:
        """Should filter by category when provided."""
        create_entry("test_tax", "Cat1 Entry", category="cat1", value="v1", seq=1)
        create_entry("test_tax", "Cat2 Entry", category="cat2", value="v2", seq=2)
        db.session.flush()

        result = get_full_taxonomy("test_tax", category="cat1")

        assert len(result) == 1
        assert result[0] == ("v1", "Cat1 Entry")

    def test_returns_sorted_by_seq(self, db: SQLAlchemy) -> None:
        """Should return entries sorted by sequence number."""
        create_entry("test_tax", "Second", value="v2", seq=20)
        create_entry("test_tax", "First", value="v1", seq=10)
        db.session.flush()

        result = get_full_taxonomy("test_tax")

        assert result[0] == ("v1", "First")
        assert result[1] == ("v2", "Second")


class TestGetFullTaxonomyCategoryValue:
    """Test suite for get_full_taxonomy_category_value function."""

    def test_returns_empty_list_when_no_entries(self, db: SQLAlchemy) -> None:
        """Should return empty list for nonexistent taxonomy."""
        result = get_full_taxonomy_category_value("nonexistent")
        assert result == []

    def test_returns_category_value_tuples(self, db: SQLAlchemy) -> None:
        """Should return list of (category, value) tuples."""
        create_entry("test_tax", "Entry", category="cat1", value="val1", seq=1)
        db.session.flush()

        result = get_full_taxonomy_category_value("test_tax")

        assert result == [("cat1", "val1")]


class TestGetTaxonomyDualSelect:
    """Test suite for get_taxonomy_dual_select function."""

    def test_returns_empty_structure_when_no_entries(self, db: SQLAlchemy) -> None:
        """Should return empty structure for nonexistent taxonomy."""
        result = get_taxonomy_dual_select("nonexistent")

        assert result["field1"] == []
        assert result["field2"] == {}

    def test_returns_dual_select_structure(self, db: SQLAlchemy) -> None:
        """Should return properly formatted dual select data."""
        create_entry("test_tax", "Entry A", category="Cat 1", value="a", seq=1)
        create_entry("test_tax", "Entry B", category="Cat 1", value="b", seq=2)
        create_entry("test_tax", "Entry C", category="Cat 2", value="c", seq=3)
        db.session.flush()

        result = get_taxonomy_dual_select("test_tax")

        # Check field1 has category tuples
        assert ("Cat 1", "Cat 1") in result["field1"]
        assert ("Cat 2", "Cat 2") in result["field1"]

        # Check field2 has entries per category
        assert "Cat 1" in result["field2"]
        assert "Cat 2" in result["field2"]
        assert len(result["field2"]["Cat 1"]) == 2
        assert len(result["field2"]["Cat 2"]) == 1


class TestUpdateEntry:
    """Test suite for update_entry function."""

    def test_creates_new_entry_if_not_exists(self, db: SQLAlchemy) -> None:
        """Should create entry if value doesn't exist."""
        result = update_entry("test_tax", "New Entry", value="new_val")
        db.session.flush()

        assert result is True
        assert check_taxonomy_exists("test_tax") is True

    def test_returns_false_if_unchanged(self, db: SQLAlchemy) -> None:
        """Should return False if entry is unchanged."""
        create_entry("test_tax", "Entry", category="cat", value="val", seq=1)
        db.session.flush()

        result = update_entry("test_tax", "Entry", category="cat", value="val", seq=1)

        assert result is False

    def test_updates_existing_entry(self, db: SQLAlchemy) -> None:
        """Should update entry when values differ."""
        create_entry("test_tax", "Old Name", category="old_cat", value="val", seq=1)
        db.session.flush()

        result = update_entry(
            "test_tax", "New Name", category="new_cat", value="val", seq=2
        )
        db.session.flush()

        assert result is True

        # Verify the update
        entries = get_full_taxonomy("test_tax")
        assert entries[0][1] == "New Name"
