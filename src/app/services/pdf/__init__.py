# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

# Register PDF handlers (import for side effects)
from . import invoice  # noqa: F401
from .base import to_pdf

__all__ = ["to_pdf"]
