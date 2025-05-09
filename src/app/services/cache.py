# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from flask_super.decorators import service


@service
class Cache:
    def __init__(self) -> None:
        self.cache = {}

    def __contains__(self, key) -> bool:
        return key in self.cache

    def __getitem__(self, key):
        return self.cache[key]

    def get(self, key):
        return self.cache.get(key)

    def set(self, key, value) -> None:
        self.cache[key] = value

    def delete(self, key) -> None:
        del self.cache[key]

    def clear(self) -> None:
        self.cache.clear()
