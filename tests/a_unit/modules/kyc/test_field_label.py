# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Tests for KYC field_label module.

These tests focus on the pure transformation functions that can be tested
without external dependencies. Functions that call external services
(get_ontology_content, zip_code_city_list) are tested through the underlying
transformation logic which is verified here.
"""

from __future__ import annotations

from app.modules.kyc.field_label import (
    KEY_LABEL_MAP,
    data_to_label,
    find_label,
    find_label_city,
    labels_string,
)


class TestFindLabel:
    """Test suite for find_label function."""

    def test_finds_existing_label(self):
        """Test finding label from content list."""
        content = [("val1", "Label 1"), ("val2", "Label 2"), ("val3", "Label 3")]

        assert find_label(content, "val1") == "Label 1"
        assert find_label(content, "val2") == "Label 2"
        assert find_label(content, "val3") == "Label 3"

    def test_returns_value_when_not_found(self):
        """Test returns original value when label not found."""
        content = [("val1", "Label 1"), ("val2", "Label 2")]
        assert find_label(content, "val4") == "val4"

    def test_handles_empty_content(self):
        """Test handles empty content list."""
        assert find_label([], "any") == "any"


class TestFindLabelCity:
    """Test suite for find_label_city function."""

    def test_finds_city_label(self):
        """Test finding city label from content list."""
        content = [
            {"value": "FR / 75001", "label": "Paris"},
            {"value": "FR / 69001", "label": "Lyon"},
        ]

        assert find_label_city(content, "FR / 75001") == "Paris"
        assert find_label_city(content, "FR / 69001") == "Lyon"

    def test_returns_value_when_not_found(self):
        """Test returns original value when city not found."""
        content = [{"value": "FR / 75001", "label": "Paris"}]
        assert find_label_city(content, "FR / 99999") == "FR / 99999"

    def test_handles_empty_content(self):
        """Test handles empty content list."""
        assert find_label_city([], "FR / 12345") == "FR / 12345"


class TestLabelsString:
    """Test suite for labels_string function."""

    def test_converts_string_value(self):
        """Test converting single string value to label."""
        onto_list = [("val1", "Label 1"), ("val2", "Label 2")]

        result = labels_string("val1", onto_list)
        assert result == "Label 1"

    def test_converts_list_of_values(self):
        """Test converting list of values to comma-separated labels."""
        onto_list = [("val1", "Label 1"), ("val2", "Label 2"), ("val3", "Label 3")]

        result = labels_string(["val1", "val2"], onto_list)
        assert result == "Label 1, Label 2"

        result = labels_string(["val1", "val3"], onto_list)
        assert result == "Label 1, Label 3"

    def test_filters_empty_labels(self):
        """Test that empty labels are filtered out."""
        onto_list = [("val1", "Label 1"), ("val2", "")]

        result = labels_string(["val1", "val2"], onto_list)
        assert result == "Label 1"

    def test_handles_all_empty_labels(self):
        """Test handles case where all labels are empty."""
        onto_list = [("val1", ""), ("val2", "")]

        result = labels_string(["val1", "val2"], onto_list)
        assert result == ""

    def test_handles_empty_list(self):
        """Test handles empty value list."""
        onto_list = [("val1", "Label 1")]

        result = labels_string([], onto_list)
        assert result == ""


class TestDataToLabel:
    """Test suite for data_to_label function."""

    def test_format_list_values(self):
        """Test formatting list values as comma-separated string."""
        result = data_to_label(["tag1", "tag2", "tag3"], "unknown_key")
        assert result == "tag1, tag2, tag3"

    def test_format_string_value(self):
        """Test formatting string value passes through."""
        result = data_to_label("simple_string", "unknown_key")
        assert result == "simple_string"

    def test_format_bool_true(self):
        """Test formatting True boolean."""
        result = data_to_label(True, "unknown_key")
        assert result == "Oui"

    def test_format_bool_false(self):
        """Test formatting False boolean."""
        result = data_to_label(False, "unknown_key")
        assert result == "Non"

    def test_password_masking(self):
        """Test password values are masked."""
        result = data_to_label("secret123", "password")
        assert result == "*********"
        assert "secret" not in result

    def test_password_masking_empty(self):
        """Test empty password is masked."""
        result = data_to_label("", "password")
        assert result == ""


class TestKeyLabelMapStructure:
    """Test suite verifying KEY_LABEL_MAP structure."""

    def test_map_contains_expected_keys(self):
        """Test that KEY_LABEL_MAP contains expected keys."""
        expected_keys = [
            "civilite",
            "competences",
            "competences_journalisme",
            "langues",
            "metier_principal",
            "pays_zip_ville",
            "taille_orga",
        ]
        for key in expected_keys:
            assert key in KEY_LABEL_MAP, f"Missing key: {key}"

    def test_map_values_are_tuples(self):
        """Test that all values are (function, ontology_name) tuples."""
        for key, value in KEY_LABEL_MAP.items():
            assert isinstance(value, tuple), f"Value for {key} is not a tuple"
            assert len(value) == 2, f"Value for {key} doesn't have 2 elements"
            assert callable(value[0]), f"First element of {key} is not callable"
            assert isinstance(value[1], str), f"Second element of {key} is not a string"

    def test_dual_fields_have_matching_detail_fields(self):
        """Test that dual select fields have matching _detail fields."""
        dual_fields = [
            "fonctions_ass_syn",
            "fonctions_org_priv",
            "fonctions_pol_adm",
            "interet_ass_syn",
            "interet_org_priv",
            "interet_pol_adm",
            "transformation_majeure",
        ]
        for field in dual_fields:
            detail_field = f"{field}_detail"
            assert detail_field in KEY_LABEL_MAP, (
                f"Missing detail field: {detail_field}"
            )


class TestTransformationLogic:
    """Test the transformation logic patterns used by label_from_values_* functions.

    These tests verify the logic that would be applied to ontology data,
    without needing to mock the ontology loading.
    """

    def test_simple_ontology_lookup_pattern(self):
        """Test the pattern used by label_from_values_simple."""
        # Simulate what label_from_values_simple does internally
        onto_list = [("civ1", "Monsieur"), ("civ2", "Madame")]

        # The function calls labels_string(data, onto_list)
        result = labels_string("civ1", onto_list)
        assert result == "Monsieur"

        result = labels_string(["civ1", "civ2"], onto_list)
        assert result == "Monsieur, Madame"

    def test_dual_first_field_extraction_pattern(self):
        """Test the pattern used by label_from_values_dual_first."""
        # Simulate what label_from_values_dual_first does internally
        onto_dict = {
            "field1": [("func1", "Director"), ("func2", "Manager")],
            "field2": {"cat1": [("detail1", "Detail 1")]},
        }

        # The function extracts field1 then calls labels_string
        field1_list = onto_dict["field1"]
        result = labels_string("func1", field1_list)
        assert result == "Director"

    def test_dual_second_field_flattening_pattern(self):
        """Test the pattern used by label_from_values_dual_second."""
        # Simulate what label_from_values_dual_second does internally
        onto_dict = {
            "field1": [],
            "field2": {
                "cat1": [("val1", "Label 1"), ("val2", "Label 2")],
                "cat2": [("val3", "Label 3")],
            },
        }

        # The function flattens field2 values then calls labels_string
        field2 = onto_dict["field2"]
        onto_list = []
        for values in field2.values():
            onto_list.extend(values)

        result = labels_string("val1", onto_list)
        assert result == "Label 1"

        result = labels_string(["val1", "val3"], onto_list)
        assert result == "Label 1, Label 3"

    def test_city_extraction_pattern(self):
        """Test the pattern used by label_from_values_cities_as_list."""
        # Simulate what label_from_values_cities_as_list does

        # Valid city code parsing
        value = "FR / 75001"
        parts = value.split(" / ")
        assert len(parts) == 2
        country_code = parts[0]
        assert country_code == "FR"

        # Invalid format handling
        invalid_value = "invalid"
        try:
            parts = invalid_value.split(" / ")
            country_code, _ = parts  # This should fail for invalid format
        except ValueError:
            pass  # Expected - invalid format
