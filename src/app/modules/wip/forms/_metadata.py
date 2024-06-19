# Copyright (c) 2021-2024 - Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

metadata = {
    "field": {
        "genre": {
            "group": "metadata",
            "key": "genre",
            "label": "Genre",
            "type": "rich-select",
            "width": 3,
            "required": True,
        },
        "section": {
            "group": "metadata",
            "key": "section",
            "label": "Rubrique",
            "type": "rich-select",
            "width": 3,
            "required": True,
        },
        "topic": {
            "group": "metadata",
            "key": "topic",
            "label": "Thématique",
            "type": "rich-select",
            "width": 6,
            "required": True,
        },
        "sector": {
            "group": "metadata",
            "key": "sector",
            "label": "Secteur",
            "type": "rich-select",
            "width": 6,
            "required": True,
        },
    }
}
