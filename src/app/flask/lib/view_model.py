# Copyright (c) 2021-2024 - Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from functools import cache

from attr import frozen
from attrs import define


@define
class ViewModel:
    _model: object
    _wrapped = True

    @classmethod
    def from_many(cls, objects: list) -> list:
        return [cls(obj) for obj in objects]

    def __getitem__(self, key):
        extra_attrs = self.extra_attrs()
        if key in extra_attrs:
            return extra_attrs[key]

        value = getattr(self._model, key)
        return value

    def __getattr__(self, key):
        extra_attrs = self.extra_attrs()
        if key in extra_attrs:
            return extra_attrs[key]

        if not hasattr(self._model, key):
            raise AttributeError

        return getattr(self._model, key)

    @cache
    def extra_attrs(self):
        return {}

    def _unwrap(self) -> object:
        return self._model


def unwrap(obj):
    if hasattr(obj, "_model"):
        return obj._model
    return obj


@frozen
class Wrapper:
    _model: object
    _wrapped = True

    def __attrs_post_init__(self) -> None:
        for k, v in self.extra_attrs().items():
            object.__setattr__(self, k, v)

    def __getattr__(self, key):
        if not hasattr(self._model, key):
            raise AttributeError

        return getattr(self._model, key)

    def extra_attrs(self):
        return {}

    def _unwrap(self) -> object:
        return self._model
