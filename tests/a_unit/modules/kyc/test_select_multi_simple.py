# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Unit tests for kyc/lib/select_multi_simple_free.py"""

from __future__ import annotations

import pytest
from typeguard import TypeCheckError

from app.modules.kyc.lib.select_multi_simple_free import (
    _dict_to_group_tom_choices,
    convert_to_tom_choices_js,
)


def test_convert_to_tom_choices_js_with_list() -> None:
    """Test convert_to_tom_choices_js converts list of tuples."""
    choices = [("val1", "Label 1"), ("val2", "Label 2")]
    result = convert_to_tom_choices_js(choices)

    assert result == [
        {"value": "val1", "label": "Label 1"},
        {"value": "val2", "label": "Label 2"},
    ]
    assert convert_to_tom_choices_js([]) == []


def test_convert_to_tom_choices_js_with_dict() -> None:
    """Test convert_to_tom_choices_js converts dict with optgroups."""
    choices = {"Group A": ["Opt 1", "Opt 2"], "Group B": ["Opt 3"]}
    result = convert_to_tom_choices_js(choices)

    assert len(result) == 3
    assert all("optgroup" in item for item in result)
    assert len([i for i in result if i["optgroup"] == "Group A"]) == 2
    assert convert_to_tom_choices_js({}) == []


def test_convert_to_tom_choices_js_invalid_type() -> None:
    """Test convert_to_tom_choices_js raises TypeError for invalid input."""
    with pytest.raises((TypeError, TypeCheckError)):
        convert_to_tom_choices_js("invalid")  # type: ignore


def test_dict_to_group_tom_choices() -> None:
    """Test _dict_to_group_tom_choices creates optgroup items."""
    result = _dict_to_group_tom_choices({"Cat": ["Item 1", "Item 2"]})

    assert result == [
        {"optgroup": "Cat", "value": "Item 1", "label": "Item 1"},
        {"optgroup": "Cat", "value": "Item 2", "label": "Item 2"},
    ]
