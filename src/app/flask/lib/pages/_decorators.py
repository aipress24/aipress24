# Copyright (c) 2021-2024 - Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from ._registry import page_registry


def page(cls):
    """Decorator for pages."""
    page_registry.add(cls)
    return cls


def expose(method):
    """Decorator to expose method as web endpoints."""
    if not hasattr(method, "_pagic_metadata"):
        method._pagic_metadata = {}
    method._pagic_metadata["exposed"] = True
    return method
