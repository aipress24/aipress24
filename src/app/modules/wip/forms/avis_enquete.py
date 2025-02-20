# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from app.lib.utils import merge_dicts

from ._metadata import metadata

avis_enquete_form = {
    "label": "Avis d'enquête",
    "model_class": "app.models.newsroom.AvisEnquete",
    "group": {
        "headers": {"label": ""},
        "metadata": {"label": "Métadonnées"},
        "dates": {"label": "Dates-clés"},
    },
    "field": {
        # Group: headers
        "titre": {
            "label": "Titre",
            "group": "headers",
            "required": True,
        },
        "contenu": {
            "label": "Brief",
            "type": "text",
            "group": "headers",
            "rows": 5,
            "required": True,
        },
        # Group: dates
        "date_debut_enquete": {
            "label": "Date/heure de début",
            "group": "dates",
            "type": "datetime",
            "width": 3,
            "required": True,
        },
        "date_fin_enquete": {
            "label": "Date/heure de fin",
            "group": "dates",
            "type": "datetime",
            "width": 3,
            "required": True,
        },
        "date_bouclage": {
            "label": "Date/heure de bouclage",
            "group": "dates",
            "type": "datetime",
            "width": 3,
            "required": True,
        },
        "date_parution_prevue": {
            "label": "Date/heure de parution prévue",
            "group": "dates",
            "type": "datetime",
            "width": 3,
            "required": True,
        },
    },
}

merge_dicts(avis_enquete_form, metadata)
