# Copyright (c) 2021-2024 - Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

import traceback
from html import escape

from loguru import logger
from markupsafe import Markup

from app.lib.names import to_kebab_case

from ._components import component_registry
from ._components2 import ComponentCaller
from ._registry import COMPONENTS

# Lets' try to unify the two paradigms:


def markup_component(name: str, *args, **kwargs) -> Markup:
    """Render a component e.g. for use in a Jinja template.

    This function is injected into the Jinja environment as a global function.

    Ex usage: {{ component('my-component', 'foo', bar='code') }}
    """

    if name in component_registry:
        component_class = component_registry[name]
        try:
            component_instance = component_class()
            component_instance.mount(*args, **kwargs)
        except Exception as e:
            traceback.print_exc()
            return Markup(f"Error rendering component {name}: {e}")
        else:
            return Markup(component_instance._initial_render())

    for component_cls in COMPONENTS.values():
        import sys

        print("markup_component,", component_cls, file=sys.stderr)

        component_name = to_kebab_case(component_cls.__name__)
        if name != component_name:
            continue

        caller = ComponentCaller(component_cls)
        return caller(*args, **kwargs)

    logger.error("Component not found: {}", name)
    return Markup(escape(f"[unknown component {name}]"))
