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
