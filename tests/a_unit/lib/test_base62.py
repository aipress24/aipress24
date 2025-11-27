# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from hypothesis import given, strategies as st

from app.lib.base62 import base62


@given(st.integers(0, 2**64))
def test_encode_decode_roundtrip(n: int) -> None:
    """Test base62 encode/decode roundtrip for arbitrary integers."""
    assert base62.decode(base62.encode(n)) == n
