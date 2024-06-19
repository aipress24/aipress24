# Copyright (c) 2021-2024 - Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from app.lib.utils import merge_dicts

from ._metadata import metadata

sujet_form = {
    "label": "Sujet",
    "model_class": "app.models.content.newsroom.Sujet",
    "group": {
        "headers": {"label": ""},
        "metadata": {"label": "Métadonnées"},
        "dates": {"label": "Dates-clés"},
    },
    "field": {
        "title": {
            "label": "Titre",
            "group": "headers",
        },
        "contenu": {
            "label": "Brief",
            "type": "text",
            "group": "headers",
            "rows": 8,
        },
        "media": {
            "label": "Média",
            "group": "headers",
            "type": "select",
            "key": "media",
            "width": 3,
        },
        # Group: dates
        "date_limite_validite": {
            "label": "Date/heure de début",
            "group": "dates",
            "type": "datetime",
            "width": 3,
        },
        "date_parution_prevue": {
            "label": "Date/heure de parution prévue",
            "group": "dates",
            "type": "datetime",
            "width": 3,
        },
    },
}

merge_dicts(sujet_form, metadata)
