# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from collections.abc import Callable

from flask.app import Flask

MACROS: list[Callable] = []


def macro(f: Callable) -> Callable:
    MACROS.append(f)
    return f


def register_macros(app: Flask) -> None:
    for macro in MACROS:
        name = getattr(macro, "__name__", str(macro))
        app.template_global(name)(macro)
