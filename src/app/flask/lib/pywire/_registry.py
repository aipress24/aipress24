# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Component registry for _components2.py."""

from __future__ import annotations

from attr import define, field
from flask_super.registry import lookup

from app.lib.names import fqdn, to_snake_case

from ._components import StaticComponent, WiredComponent, component_registry
from ._components2 import Component, ComponentCaller

# Dict class-name -> class
COMPONENTS: dict[str, type] = {}


@define
class ComponentRegistry:
    _components: dict[str, type] = field(factory=dict)

    def __getitem__(self, key: str) -> type:
        return self._components[key]

    def add(self, cls: type[Component]) -> None:
        assert issubclass(cls, Component)
        self._components[fqdn(cls)] = cls


# TODO:
# component_registry = ComponentRegistry()


def get_components():
    return COMPONENTS


def component(cls: type[Component]):
    """Decorator for pages."""

    assert issubclass(cls, Component)
    COMPONENTS[fqdn(cls)] = cls
    return cls


def register_components(app) -> None:
    for cls in COMPONENTS.values():
        _register_component(app, cls)


def _register_component(app, component_cls) -> None:
    caller = ComponentCaller(component_cls)
    name = to_snake_case(component_cls.__name__)
    app.template_global(name)(caller)


# Wired components
def register_wired_component(app, component_cls) -> None:
    name = component_cls._get_name()
    component_registry[name] = component_cls


def register_wired_components(app) -> None:
    components = lookup(WiredComponent)
    for component in components:
        register_wired_component(app, component)
    static_components = lookup(StaticComponent)
    for component in static_components:
        register_wired_component(app, component)
