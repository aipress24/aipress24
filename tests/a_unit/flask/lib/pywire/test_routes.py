# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Unit tests for flask/lib/pywire/_routes.py."""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

import pytest
from jinja2 import Template
from werkzeug.exceptions import BadRequest

from app.flask.lib.pywire._components import StaticComponent, WiredComponent
from app.flask.lib.pywire._routes import livewire_fire_event, livewire_sync_input

if TYPE_CHECKING:
    from flask import Flask


class MockComponent:
    """Mock component for testing livewire functions."""

    _attrs: ClassVar = ["simple_attr", "nested", "data"]
    _listeners: ClassVar = ["my_event", "click-handler"]

    def __init__(self):
        self.simple_attr = None
        self.nested = {"level1": {"level2": None}}
        self.event_called = False
        self.event_params = None

    def on_my_event(self, *params):
        self.event_called = True
        self.event_params = params

    def on_click_handler(self, *params):
        self.event_called = True
        self.event_params = params


class TestLivewireSyncInput:
    """Test livewire_sync_input function."""

    def test_simple_attribute_sync(self):
        """Sets simple top-level attribute."""
        component = MockComponent()
        payload = {"name": "simple_attr", "value": "test_value"}

        livewire_sync_input(component, payload)

        assert component.simple_attr == "test_value"

    def test_nested_attribute_sync_two_levels(self):
        """Sets nested attribute with dot notation."""
        component = MockComponent()
        payload = {"name": "nested.level1.level2", "value": "deep_value"}

        livewire_sync_input(component, payload)

        assert component.nested["level1"]["level2"] == "deep_value"

    def test_nested_attribute_sync_one_level(self):
        """Sets single-level nested attribute."""
        component = MockComponent()
        component.data = {"key": None}
        payload = {"name": "data.key", "value": "updated"}

        livewire_sync_input(component, payload)

        assert component.data["key"] == "updated"


class TestLivewireFireEvent:
    """Test livewire_fire_event function."""

    def test_fires_simple_event(self):
        """Fires event with underscored method name."""
        component = MockComponent()
        payload = {"event": "my_event", "params": ["arg1", "arg2"]}

        livewire_fire_event(component, payload)

        assert component.event_called is True
        assert component.event_params == ("arg1", "arg2")

    def test_converts_dashes_to_underscores(self):
        """Converts dashes in event name to underscores for method lookup."""
        component = MockComponent()
        payload = {"event": "click-handler", "params": []}

        livewire_fire_event(component, payload)

        assert component.event_called is True

    def test_fires_event_with_no_params(self):
        """Fires event with empty params list."""
        component = MockComponent()
        payload = {"event": "my_event", "params": []}

        livewire_fire_event(component, payload)

        assert component.event_called is True
        assert component.event_params == ()

    def test_refuses_an_undeclared_event(self):
        """Only the events a component lists in `_listeners` reach it."""
        component = MockComponent()
        component.on_secret = lambda: setattr(component, "event_called", True)
        payload = {"event": "secret", "params": []}

        with pytest.raises(BadRequest):
            livewire_fire_event(component, payload)

        assert component.event_called is False


class _StaticStub(StaticComponent):
    def _get_template(self) -> Template:
        return Template("from file")


class _WiredStub(WiredComponent):
    def _get_template(self) -> Template:
        return Template("from file")


@pytest.mark.parametrize("component_class", [_StaticStub, _WiredStub])
def test_format_string_attribute_is_not_rendered(
    app: Flask, component_class: type[_StaticStub | _WiredStub]
) -> None:
    component = component_class(id="component-id")
    component._restore({"_template": "{self._id}"})

    with app.test_request_context():
        assert component.render_template() == "from file"
