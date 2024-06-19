# Copyright (c) 2021-2024 - Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from cleez.colors import blue
from flask.cli import with_appcontext
from flask_super.cli import command

from app.flask.lib.pywire import component_registry, get_components
from app.lib.names import to_kebab_case


@command(short_help="List components")
@with_appcontext
def components() -> None:
    print(blue("Static components:"))
    registry1 = component_registry
    for k, v in sorted(registry1.items()):
        print(f"{k}: {v}")

    print()

    print(blue("Live components:"))
    for component_cls in get_components().values():
        component_name = to_kebab_case(component_cls.__name__)
        print(f"{component_name}: {component_cls}")
