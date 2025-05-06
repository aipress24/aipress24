# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from hypothesis import given, strategies as st

from app.lib.base62 import base62


def test_1() -> None:
    for i in range(1000):
        assert base62.decode(base62.encode(i)) == i


@given(st.integers(0, 2**64))
def test_with_hypothesis(n) -> None:
    assert base62.decode(base62.encode(n)) == n
