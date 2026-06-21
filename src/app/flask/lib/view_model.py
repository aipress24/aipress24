"""View model and wrapper classes for presentation layer object decoration."""
# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from attr import frozen
from attrs import define, field


@define
class ViewModel:
    """Wrapper class that adds presentation logic to model objects."""

    _model: object
    _wrapped = True
    # Memoized result of `extra_attrs()`. Without this the base recomputed
    # the whole bundle on EVERY attribute access — catastrophic for VMs whose
    # extra_attrs runs queries (see swork UserVM).
    _extra_cache: dict | None = field(init=False, default=None)

    @classmethod
    def from_many(cls, objects: list) -> list:
        """Create view models from a list of objects."""
        return [cls(obj) for obj in objects]

    def _get_extra(self) -> dict:
        """Return `extra_attrs()`, computed at most once per instance."""
        if self._extra_cache is None:
            self._extra_cache = self.extra_attrs()
        return self._extra_cache

    def _lazy(self, key, factory):
        """Compute `factory()` once and cache it under `key`. Lets a subclass
        expose an expensive attribute as a property without recomputing it on
        repeated reads (e.g. `profile.followers` read twice in a template)."""
        cache = self._get_extra()
        if key not in cache:
            cache[key] = factory()
        return cache[key]

    def __getitem__(self, key):
        """Dictionary-style access to model attributes and extra attributes."""
        extra_attrs = self._get_extra()
        if key in extra_attrs:
            return extra_attrs[key]

        value = getattr(self._model, key)
        return value

    def __getattr__(self, key):
        """Attribute access to model attributes and extra attributes."""
        extra_attrs = self._get_extra()
        if key in extra_attrs:
            return extra_attrs[key]

        if not hasattr(self._model, key):
            raise AttributeError

        return getattr(self._model, key)

    def extra_attrs(self) -> dict:
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
