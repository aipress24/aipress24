# Copyright (c) 2021-2024 - Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from collections import defaultdict
from typing import Any


class Directory:
    objects: list[Any]
    directory: dict[str, list[Any]]
    key: str
    vm_class: type | None = None

    def __init__(self, objects: list, key: str = "name") -> None:
        self.objects = list(objects)
        self.key = key

        self.objects.sort(key=self.sorter)

        self.directory = defaultdict(list)
        for obj in self.objects:
            key = self.get_key(obj)
            self.directory[key].append(self.wrap(obj))

    def wrap(self, obj: Any) -> Any:
        if self.vm_class is None:
            return obj
        return self.vm_class(obj)

    def sorter(self, obj: Any) -> str:
        return getattr(obj, self.key)

    def get_key(self, obj: Any) -> str:
        c = getattr(obj, self.key)
        if c:
            return c[0].upper()
        return "?"

    # Delegate to the directory
    def keys(self):
        return self.directory.keys()

    def __getitem__(self, item):
        return self.directory[item]
