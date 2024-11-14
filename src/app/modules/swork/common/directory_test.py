# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from dataclasses import dataclass

from . import Directory


@dataclass
class Item:
    name: str


def test_directory() -> None:
    items = [Item("toto"), Item("titi"), Item("tata")]
    directory = Directory(items)

    keys = list(directory.keys())
    assert keys == ["T"]
    assert [item.name for item in directory.directory["T"]] == ["tata", "titi", "toto"]
