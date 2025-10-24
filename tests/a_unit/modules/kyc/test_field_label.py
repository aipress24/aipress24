# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from unittest.mock import patch

from app.modules.kyc.field_label import (
    country_code_to_label,
    country_zip_code_to_city,
    find_label,
    find_label_city,
    label_from_values_cities,
    label_from_values_cities_as_list,
    label_from_values_dual_first,
    label_from_values_dual_second,
    label_from_values_simple,
    labels_string,
)


def test_find_label():
    """Test finding label from content list."""
    content = [("val1", "Label 1"), ("val2", "Label 2"), ("val3", "Label 3")]

    assert find_label(content, "val1") == "Label 1"
    assert find_label(content, "val2") == "Label 2"
    assert find_label(content, "val3") == "Label 3"
    # Returns value if not found
    assert find_label(content, "val4") == "val4"


def test_find_label_city():
    """Test finding city label from content list."""
    content = [
        {"value": "FR / 75001", "label": "Paris"},
        {"value": "FR / 69001", "label": "Lyon"},
    ]

    assert find_label_city(content, "FR / 75001") == "Paris"
    assert find_label_city(content, "FR / 69001") == "Lyon"
    # Returns value if not found
    assert find_label_city(content, "FR / 99999") == "FR / 99999"


def test_labels_string_with_string():
    """Test converting string value to labels."""
    onto_list = [("val1", "Label 1"), ("val2", "Label 2")]

    result = labels_string("val1", onto_list)
    assert result == "Label 1"


def test_labels_string_with_list():
    """Test converting list of values to comma-separated labels."""
    onto_list = [("val1", "Label 1"), ("val2", "Label 2"), ("val3", "Label 3")]

    result = labels_string(["val1", "val2"], onto_list)
    assert result == "Label 1, Label 2"

    result = labels_string(["val1", "val3"], onto_list)
    assert result == "Label 1, Label 3"


def test_labels_string_filters_empty():
    """Test that empty labels are filtered out."""
    onto_list = [("val1", "Label 1"), ("val2", "")]

    result = labels_string(["val1", "val2"], onto_list)
    assert result == "Label 1"


@patch("app.modules.kyc.field_label.get_ontology_content")
def test_label_from_values_simple(mock_get_ontology):
    """Test label_from_values_simple."""
    mock_get_ontology.return_value = [("val1", "Label 1"), ("val2", "Label 2")]

    result = label_from_values_simple("val1", "key", "ontology")
    assert result == "Label 1"

    result = label_from_values_simple(["val1", "val2"], "key", "ontology")
    assert result == "Label 1, Label 2"

    mock_get_ontology.assert_called_with("ontology")


@patch("app.modules.kyc.field_label.get_ontology_content")
def test_label_from_values_dual_first(mock_get_ontology):
    """Test label_from_values_dual_first."""
    mock_get_ontology.return_value = {
        "field1": [("val1", "Label 1"), ("val2", "Label 2")],
        "field2": {},
    }

    result = label_from_values_dual_first("val1", "key", "ontology")
    assert result == "Label 1"

    result = label_from_values_dual_first(["val1", "val2"], "key", "ontology")
    assert result == "Label 1, Label 2"


@patch("app.modules.kyc.field_label.get_ontology_content")
def test_label_from_values_dual_second(mock_get_ontology):
    """Test label_from_values_dual_second."""
    mock_get_ontology.return_value = {
        "field1": [],
        "field2": {
            "cat1": [("val1", "Label 1"), ("val2", "Label 2")],
            "cat2": [("val3", "Label 3")],
        },
    }

    result = label_from_values_dual_second("val1", "key", "ontology")
    assert result == "Label 1"

    result = label_from_values_dual_second(["val1", "val3"], "key", "ontology")
    assert result == "Label 1, Label 3"


@patch("app.modules.kyc.field_label.zip_code_city_list")
def test_label_from_values_cities_as_list(mock_zip_code):
    """Test label_from_values_cities_as_list."""
    mock_zip_code.return_value = [
        {"value": "FR / 75001", "label": "Paris"},
        {"value": "FR / 69001", "label": "Lyon"},
    ]

    result = label_from_values_cities_as_list("FR / 75001")
    assert result == ["Paris"]

    result = label_from_values_cities_as_list(["FR / 75001", "FR / 69001"])
    assert result == ["Paris", "Lyon"]

    # Test with empty/malformed values
    result = label_from_values_cities_as_list(["  ", "invalid"])
    assert result == []


@patch("app.modules.kyc.field_label.zip_code_city_list")
def test_label_from_values_cities(mock_zip_code):
    """Test label_from_values_cities."""
    mock_zip_code.return_value = [
        {"value": "FR / 75001", "label": "Paris"},
        {"value": "FR / 69001", "label": "Lyon"},
    ]

    result = label_from_values_cities("FR / 75001", "key", "ontology")
    assert result == "Paris"

    result = label_from_values_cities(["FR / 75001", "FR / 69001"], "key", "ontology")
    assert result == "Paris, Lyon"


@patch("app.modules.kyc.field_label.get_ontology_content")
def test_country_code_to_label(mock_get_ontology):
    """Test country_code_to_label."""
    mock_get_ontology.return_value = [("FR", "France"), ("US", "United States")]

    result = country_code_to_label("FR")
    assert result == "France"

    mock_get_ontology.assert_called_with("pays")


@patch("app.modules.kyc.field_label.zip_code_city_list")
def test_country_zip_code_to_city(mock_zip_code):
    """Test country_zip_code_to_city."""
    mock_zip_code.return_value = [
        {"value": "FR / 75001", "label": "Paris"},
    ]

    result = country_zip_code_to_city("FR / 75001")
    assert result == "Paris"

    # Test with invalid format
    result = country_zip_code_to_city("invalid")
    assert result == ""


def test_data_to_label_format_list():
    """Test data_to_label with formatting list/str/bool values."""
    from app.modules.kyc.field_label import data_to_label

    # Test with list
    result = data_to_label(["tag1", "tag2", "tag3"], "unknown_key")
    assert result == "tag1, tag2, tag3"

    # Test with string
    result = data_to_label("simple_string", "unknown_key")
    assert result == "simple_string"

    # Test with bool True
    result = data_to_label(True, "unknown_key")
    assert result == "Oui"

    # Test with bool False
    result = data_to_label(False, "unknown_key")
    assert result == "Non"

    # Test password masking
    result = data_to_label("secret123", "password")
    assert result == "*********"
