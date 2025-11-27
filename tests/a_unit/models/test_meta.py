# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from app.models.meta import get_label, get_meta_attr


class A:
    class Meta:
        test = 1


class B(A):
    pass


class C(A):
    class Meta:
        test = 2


class NoMeta:
    """Class without Meta."""

    pass


class WithLabel:
    class Meta:
        type_label = "Custom Label"


def test_get_meta_attr() -> None:
    assert get_meta_attr(A, "test") == 1
    assert get_meta_attr(A(), "test") == 1
    assert get_meta_attr(B, "test") == 1
    assert get_meta_attr(B(), "test") == 1
    assert get_meta_attr(C, "test") == 2
    assert get_meta_attr(C(), "test") == 2


def test_get_meta_attr_no_meta_class() -> None:
    """Test get_meta_attr returns default when object has no Meta class."""
    assert get_meta_attr(NoMeta, "test") is None
    assert get_meta_attr(NoMeta(), "test") is None
    assert get_meta_attr(NoMeta, "test", default="fallback") == "fallback"


def test_get_meta_attr_missing_attribute() -> None:
    """Test get_meta_attr returns default when attribute doesn't exist on instance."""
    # Test with instance - returns default when attribute doesn't exist
    assert get_meta_attr(A(), "nonexistent") is None
    assert get_meta_attr(A(), "nonexistent", default=42) == 42


def test_get_label() -> None:
    """Test get_label returns type_label from Meta."""
    # Test with instances
    assert get_label(WithLabel()) == "Custom Label"


def test_get_label_no_type_label() -> None:
    """Test get_label returns empty string when no type_label."""
    # Test with instances
    assert get_label(A()) == ""
    assert get_label(NoMeta()) == ""
