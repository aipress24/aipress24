# Copyright (c) 2021-2024 - Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from typing import Any


class Adapter:
    _adaptee_id: str

    def _get_adaptee(self):
        return getattr(self, self._adaptee_id)

    # @property
    # def _obj(self):
    #     return getattr(self, self._adaptee_id)

    @property
    def id(self) -> int:
        return self._get_adaptee().id


def adapt(obj: Any, cls: type) -> Any:
    if isinstance(obj, cls):
        return obj
    return cls(obj)


def unadapt(obj: Any) -> Any:
    if isinstance(obj, Adapter):
        return obj._get_adaptee()
    return obj
