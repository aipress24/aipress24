# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from ._components import StaticComponent, WiredComponent, component_registry
from ._components2 import Component
from ._markup import markup_component
from ._registry import (
    component,
    get_components,
    register_components,
    register_wired_component,
    register_wired_components,
)
from ._routes import register_pywire

__all__ = [
    "Component",
    "StaticComponent",
    "WiredComponent",
    "component",
    "component_registry",
    "get_components",
    "markup_component",
    "register_components",
    "register_pywire",
    "register_wired_component",
    "register_wired_components",
]
