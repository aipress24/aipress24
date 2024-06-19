# Copyright (c) 2021-2024 - Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from ._decorators import expose, page
from ._page import Page
from ._registry import PageRegistry, get_pages, page_registry, register_pages

__all__ = [
    "Page",
    "PageRegistry",
    "expose",
    "get_pages",
    "page",
    "page_registry",
    "register_pages",
]
