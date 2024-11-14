# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from app.lib.utils import merge_dicts

from ._metadata import metadata

article_form = {
    "label": "Article",
    "model_class": "app.models.content.Article",
    "group": {
        "headers": {"label": ""},
        "contenu": {"label": "Contenu de l'article"},
        "metadata": {"label": "Métadonnées de l'article"},
        "copyright": {"label": "Copyright de l'article"},
        "dates": {"label": "Dates-clés de l'article"},
    },
    "field": {
        # Group: headers
        "titre": {
            "label": "Titre",
            "group": "headers",
            "required": True,
        },
        "chapo": {
            "label": "Chapô",
            "group": "headers",
            "type": "text",
            "rows": 5,
        },
        # Group: contenu
        "contenu": {
            "label": "Contenu",
            "type": "rich-text",
            "group": "contenu",
            "rows": 20,
            "required": True,
        },
        # Group: copyright
        "copyright": {
            "label": "Mention du copyright",
            "group": "copyright",
            "type": "rich-select",
            "key": "copyright-mention",
            "width": 3,
        },
        # Group: dates
        "date_parution_prevue": {
            "label": "Date/heure de parution prévue",
            "group": "dates",
            "type": "datetime",
            "width": 3,
        },
        "date_publication_aip24": {
            "label": "Date/heure de publication sur AIP24",
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

merge_dicts(article_form, metadata)
