# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from app.lib.utils import merge_dicts

from ._metadata import metadata

commande_form = {
    "label": "Commande",
    "model_class": "app.models.content.newsroom.Commande",
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
            "rows": 5,
        },
        # Group: dates
        "date_limite_validite": {
            "label": "Date/heure de début",
            "group": "dates",
            "type": "datetime",
            "width": 3,
        },
        "date_bouclage": {
            "label": "Date/heure de bouclage",
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
        "date_paiement": {
            "label": "Date/heure de paiement",
            "group": "dates",
            "type": "datetime",
            "width": 3,
        },
    },
}

merge_dicts(commande_form, metadata)
