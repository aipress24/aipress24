# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only
from __future__ import annotations

import sys
from typing import Any


def info(*args: Any) -> None:
    msg = " ".join(str(x) for x in args)
    print(f"{msg}", file=sys.stderr)


def warning(*args: Any) -> None:
    msg = " ".join(str(x) for x in args)
    print(f"Warning: {msg}", file=sys.stderr)
