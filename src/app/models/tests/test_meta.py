# Copyright (c) 2021-2024 - Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from ..meta import get_meta_attr


class A:
    class Meta:
        test = 1


class B(A):
    pass


class C(A):
    class Meta:
        test = 2


def test_get_meta_attr() -> None:
    assert get_meta_attr(A, "test") == 1
    assert get_meta_attr(A(), "test") == 1
    assert get_meta_attr(B, "test") == 1
    assert get_meta_attr(B(), "test") == 1
    assert get_meta_attr(C, "test") == 2
    assert get_meta_attr(C(), "test") == 2
