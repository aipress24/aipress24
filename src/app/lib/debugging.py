# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Add devtools `debug` function to builtins.

Both `snoop` and `devtools` are optional (dev-only) dependencies: in
production images we fall back silently to `print`.
"""

from __future__ import annotations

import contextlib
from typing import Any

debug: Any = print

with contextlib.suppress(ImportError):
    from devtools import debug  # type: ignore[assignment,no-redef]


def install() -> None:
    __builtins__["debug"] = debug
    with contextlib.suppress(ImportError):
        import snoop  # noqa: PLC0415

        snoop.install()
