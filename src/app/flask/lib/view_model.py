"""View model and wrapper classes for presentation layer object decoration."""
# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from functools import cache

from attr import frozen
from attrs import define


@define
class ViewModel:
    """Wrapper class that adds presentation logic to model objects."""

    _model: object
    _wrapped = True

    @classmethod
    def from_many(cls, objects: list) -> list:
        """Create view models from a list of objects."""
        return [cls(obj) for obj in objects]

    def __getitem__(self, key):
        """Dictionary-style access to model attributes and extra attributes."""
        extra_attrs = self.extra_attrs()
        if key in extra_attrs:
            return extra_attrs[key]

        value = getattr(self._model, key)
        return value

    def __getattr__(self, key):
        """Attribute access to model attributes and extra attributes."""
        extra_attrs = self.extra_attrs()
        if key in extra_attrs:
            return extra_attrs[key]

        if not hasattr(self._model, key):
            raise AttributeError

        return getattr(self._model, key)

    @cache
    def extra_attrs(self):
        """Override to provide additional attributes for the view model."""
        return {}

    def _unwrap(self) -> object:
        """Return the underlying model object."""
        return self._model


def unwrap(obj):
    """Extract the underlying model from a wrapped object if it exists."""
    if hasattr(obj, "_model"):
        return obj._model
    return obj


@frozen
class Wrapper:
    """Immutable wrapper class for decorating model objects."""

    _model: object
    _wrapped = True

    def __attrs_post_init__(self) -> None:
        """Initialize extra attributes after object creation."""
        for k, v in self.extra_attrs().items():
            object.__setattr__(self, k, v)

    def __getattr__(self, key):
        """Proxy attribute access to the underlying model."""
        if not hasattr(self._model, key):
            raise AttributeError

        return getattr(self._model, key)

    def extra_attrs(self):
        """Override to provide additional attributes for the wrapper."""
        return {}

    def _unwrap(self) -> object:
        """Return the underlying model object."""
        return self._model
