# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""UI-facing list of search collections.

Derived from :data:`registry.REGISTRY` — the per-type metadata
(``label`` / ``icon`` / type-discriminator) lives there. This module
just glues the registry onto an ``"all"`` aggregator entry at the top
so the sidebar can show the "everything" bucket.

If you want to change a label or an icon, edit ``registry.py``, not
this file.
"""

from __future__ import annotations

from typing import Any

from .registry import REGISTRY


def _collection_from(entry) -> dict[str, Any]:
    # The view layer expects a single string when there is only one
    # discriminator, a list when there are many (so the engine can OR
    # them). Preserving that quirk keeps ``views.py`` unchanged.
    type_value: str | list[str]
    if len(entry.doc_types) == 1:
        type_value = entry.doc_types[0]
    else:
        type_value = list(entry.doc_types)
    return {
        "name": entry.ui_name,
        "label": entry.label,
        "icon": entry.icon,
        "type": type_value,
    }


COLLECTIONS: list[dict[str, Any]] = [
    {
        "name": "all",
        "label": "Tout",
        "icon": "rectangle-stack",
        "type": None,
    },
    *(_collection_from(entry) for entry in REGISTRY),
]
