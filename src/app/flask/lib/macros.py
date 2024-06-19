# Copyright (c) 2021-2024 - Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from collections.abc import Callable

from flask.app import Flask

MACROS = []


def macro(f: Callable) -> Callable:
    MACROS.append(f)
    return f


def register_macros(app: Flask) -> None:
    for macro in MACROS:
        app.template_global(macro.__name__)(macro)
