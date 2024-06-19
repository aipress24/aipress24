# Copyright (c) 2021-2024 - Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Add devtools `debug` function to builtins."""

from __future__ import annotations

from typing import Any

import snoop

debug: Any = None

try:
    from devtools import debug
except ImportError:
    debug = print


def install() -> None:
    if debug is not None:
        __builtins__["debug"] = debug
        snoop.install()
