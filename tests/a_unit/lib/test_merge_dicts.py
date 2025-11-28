# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Unit tests for lib/utils.py merge_dicts function."""

from __future__ import annotations

from app.lib.utils import merge_dicts


def test_merge_dicts_flat_and_overwrite() -> None:
    """Test flat merge and value overwriting."""
    target = {"a": 1, "b": 2}
    other = {"b": 99, "c": 3}

    result = merge_dicts(target, other)

    assert result == {"a": 1, "b": 99, "c": 3}
    assert result is target  # Mutates target


def test_merge_dicts_nested() -> None:
    """Test deep merge of nested dicts."""
    target = {"a": {"x": 1, "y": 2}, "b": 3}
    other = {"a": {"y": 99, "z": 100}}

    result = merge_dicts(target, other)

    assert result == {"a": {"x": 1, "y": 99, "z": 100}, "b": 3}


def test_merge_dicts_type_mismatch() -> None:
    """Test merge with type mismatches (scalar <-> dict)."""
    # Scalar replaced by dict
    target1 = {"a": "scalar"}
    merge_dicts(target1, {"a": {"nested": "value"}})
    assert target1 == {"a": {"nested": "value"}}

    # Dict replaced by scalar
    target2 = {"a": {"nested": "value"}}
    merge_dicts(target2, {"a": "scalar"})
    assert target2 == {"a": "scalar"}


def test_merge_dicts_empty() -> None:
    """Test merge with empty dicts."""
    # Empty target
    target1 = {}
    merge_dicts(target1, {"a": 1})
    assert target1 == {"a": 1}

    # Empty other
    target2 = {"a": 1}
    merge_dicts(target2, {})
    assert target2 == {"a": 1}
