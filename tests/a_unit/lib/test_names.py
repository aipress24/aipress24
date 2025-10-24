# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from app.lib.names import fqdn, to_kebab_case, to_snake_case


def test_to_kebab_case() -> None:
    assert to_kebab_case("FooBar") == "foo-bar"


def test_to_snake_case() -> None:
    assert to_snake_case("FooBar") == "foo_bar"


def test_fqdn() -> None:
    class Foo:
        pass

    assert fqdn(Foo) == "test_names.Foo"
