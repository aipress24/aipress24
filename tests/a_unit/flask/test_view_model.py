# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Unit tests for flask/lib/view_model.py"""

from __future__ import annotations

import pytest

from app.flask.lib.view_model import ViewModel, Wrapper, unwrap


class StubModel:
    """Stub model for testing view models."""

    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


class SimpleViewModel(ViewModel):
    """Simple view model that overrides extra_attrs to avoid caching issue."""

    def extra_attrs(self):
        return {}


class CustomViewModel(ViewModel):
    """Custom view model with extra attributes."""

    def extra_attrs(self):
        return {"computed_value": f"computed:{self._model.name}"}


def test_viewmodel_from_many() -> None:
    """Test ViewModel.from_many creates list of view models."""
    models = [StubModel(id=1), StubModel(id=2), StubModel(id=3)]
    result = ViewModel.from_many(models)

    assert len(result) == 3
    assert all(isinstance(vm, ViewModel) for vm in result)
    assert [vm._model.id for vm in result] == [1, 2, 3]


def test_viewmodel_attribute_access() -> None:
    """Test ViewModel proxies attribute access and provides extra_attrs."""
    model = StubModel(name="example", value=42)
    vm = CustomViewModel(model)

    # Proxied attributes
    assert vm.name == "example"
    assert vm.value == 42
    # Extra attributes
    assert vm.computed_value == "computed:example"
    # Dictionary access
    assert vm["name"] == "example"
    assert vm["computed_value"] == "computed:example"


def test_viewmodel_raises_for_missing_attr() -> None:
    """Test ViewModel raises AttributeError for missing attributes."""
    vm = SimpleViewModel(StubModel(name="test"))
    with pytest.raises(AttributeError):
        _ = vm.nonexistent


def test_unwrap_extracts_model() -> None:
    """Test unwrap function extracts underlying model."""
    model = StubModel(id=123)
    vm = ViewModel(model)

    assert vm._unwrap() is model
    assert unwrap(vm) is model
    assert unwrap(model) is model  # Non-wrapped returns same object


def test_viewmodel_memoizes_extra_attrs() -> None:
    """extra_attrs() is computed once per instance, not on every access
    (the fix for the swork member-page N+1)."""
    calls = []

    class CountingVM(ViewModel):
        def extra_attrs(self):
            calls.append(1)
            return {"a": 1, "b": 2}

    vm = CountingVM(StubModel(name="x"))
    _ = vm.a
    _ = vm.b
    _ = vm.a
    _ = vm["b"]
    assert len(calls) == 1


def test_viewmodel_lazy_caches_factory() -> None:
    """_lazy computes its factory once and caches the result, so a heavy
    property read twice in a template runs one query, not two."""
    factory_calls = []

    class LazyVM(ViewModel):
        def extra_attrs(self):
            return {"light": 1}

        @property
        def heavy(self):
            return self._lazy("heavy", self._compute_heavy)

        def _compute_heavy(self):
            factory_calls.append(1)
            return [1, 2, 3]

    vm = LazyVM(StubModel(name="x"))
    assert vm.heavy == [1, 2, 3]
    assert vm.heavy == [1, 2, 3]
    assert len(factory_calls) == 1


def test_wrapper_proxies_and_is_frozen() -> None:
    """Test Wrapper proxies attributes and is immutable."""
    model = StubModel(label="test", count=10)
    wrapper = Wrapper(model)

    assert wrapper.label == "test"
    assert wrapper.count == 10
    assert wrapper._unwrap() is model

    with pytest.raises(AttributeError):
        _ = wrapper.missing_attr

    with pytest.raises(Exception):  # FrozenInstanceError
        wrapper.label = "changed"
