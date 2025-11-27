# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

import pytest

from app.lib.utils import merge_dicts

PARAMS = [
    ({}, {}, {}),
    ({1: 2}, {}, {1: 2}),
    ({3: 4}, {1: 2}, {1: 2, 3: 4}),
    ({3: 4, 5: {6: 7}}, {1: 2}, {1: 2, 3: 4, 5: {6: 7}}),
    ({3: 4, 5: {6: 7}}, {1: 2, 3: {7: 8}}, {1: 2, 3: {7: 8}, 5: {6: 7}}),
]


@pytest.mark.parametrize(("d1", "d2", "expected"), PARAMS)
def test_merge_dicts_commutative(d1, d2, expected) -> None:
    """Test merge_dicts produces expected result in both orders."""
    assert merge_dicts(d1, d2) == expected
    assert merge_dicts(d2, d1) == expected
