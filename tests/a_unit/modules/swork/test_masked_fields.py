# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Unit tests for swork/masked_fields.py"""

from __future__ import annotations

from app.modules.swork.masked_fields import MaskFields


def test_mask_fields_add_and_remove() -> None:
    """Test adding and removing fields from mask."""
    mask = MaskFields()

    mask.add_field("email")
    mask.add_field("phone")
    assert mask.masked == {"email", "phone"}

    mask.remove_field("email")
    assert mask.masked == {"phone"}

    # Removing non-existent field is safe
    mask.remove_field("nonexistent")
    assert mask.masked == {"phone"}


def test_mask_fields_add_message() -> None:
    """Test adding messages with comma separator."""
    mask = MaskFields()

    mask.add_message("First")
    assert mask.story == "First"

    mask.add_message("Second")
    mask.add_message("Third")
    assert mask.story == "First, Second, Third"


def test_mask_fields_duplicate_field_ignored() -> None:
    """Test adding duplicate field doesn't create duplicates."""
    mask = MaskFields()

    mask.add_field("email")
    mask.add_field("email")

    assert len(mask.masked) == 1
