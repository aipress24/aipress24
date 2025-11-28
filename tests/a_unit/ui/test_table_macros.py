# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Unit tests for ui/macros/table.py"""

from __future__ import annotations

import pytest
from markupsafe import Markup

from app.ui.macros.table import format_value, make_columns


def test_make_columns_from_strings() -> None:
    """Test make_columns converts string names to dicts."""
    columns = ["name", "price", "quantity"]
    result = make_columns(columns)

    assert len(result) == 3
    assert result[0] == {"name": "name", "label": "Name"}
    assert result[1] == {"name": "price", "label": "Price"}
    assert result[2] == {"name": "quantity", "label": "Quantity"}


def test_make_columns_from_dicts() -> None:
    """Test make_columns preserves dict columns."""
    columns = [
        {"name": "brand.name", "label": "Brand"},
        {"name": "sku", "label": "SKU"},
    ]
    result = make_columns(columns)

    assert len(result) == 2
    assert result[0] == {"name": "brand.name", "label": "Brand"}
    assert result[1] == {"name": "sku", "label": "SKU"}


def test_make_columns_mixed() -> None:
    """Test make_columns handles mixed string and dict inputs."""
    columns = ["name", {"name": "brand.name", "label": "Brand"}, "price"]
    result = make_columns(columns)

    assert len(result) == 3
    assert result[0] == {"name": "name", "label": "Name"}
    assert result[1] == {"name": "brand.name", "label": "Brand"}
    assert result[2] == {"name": "price", "label": "Price"}


def test_make_columns_invalid_input() -> None:
    """Test make_columns raises ValueError for invalid input."""
    with pytest.raises(ValueError, match="Can't match value"):
        make_columns([123])  # Invalid type


def test_format_value_string() -> None:
    """Test format_value returns string as-is."""
    assert format_value("hello") == "hello"
    assert format_value("test string") == "test string"


def test_format_value_integer() -> None:
    """Test format_value converts integer to string."""
    assert format_value(42) == "42"
    assert format_value(0) == "0"
    assert format_value(-100) == "-100"


def test_format_value_float() -> None:
    """Test format_value formats float to 2 decimal places."""
    assert format_value(3.14159) == "3.14"
    assert format_value(10.0) == "10.00"
    assert format_value(0.5) == "0.50"


def test_format_value_nested_dict() -> None:
    """Test format_value extracts value from nested dict."""
    assert format_value({"value": "inner"}) == "inner"
    assert format_value({"value": 42}) == "42"
    assert format_value({"value": {"value": "deep"}}) == "deep"


def test_format_value_download_type() -> None:
    """Test format_value handles download type with Markup."""
    result = format_value({"type": "download", "value": "https://example.com/file.pdf"})
    assert isinstance(result, Markup)
    assert "https://example.com/file.pdf" in result


def test_format_value_invalid_input() -> None:
    """Test format_value raises ValueError for invalid input."""
    with pytest.raises(ValueError, match="Can't match value"):
        format_value([1, 2, 3])  # Invalid type
