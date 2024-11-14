# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from app.models.content import Article, Image, PressEvent, PublicEvent, TrainingEvent
from app.modules.wip.models.newsroom import Sujet

LABELS_FOR_CONTENT_TYPES = {
    "article": "Article",
    "press-release": "Communiqué de presse",
    "press-event": "Evénement de presse",
    "public-event": "Evénement public",
    "training-event": "Formation",
    "editorial-product": "Produit éditorial",
    "image": "Image",
    "video": "Vidéo",
    "pitch": "Proposition de sujet",
    "mission": "Proposition de mission",
    "call-for-witnesses": "Avis d'enquête",
}

DOC_CLASSES = {
    "article": Article,
    "newsroom/sujet": Sujet,
    "image": Image,
    "press-event": PressEvent,
    "public-event": PublicEvent,
    "training-event": TrainingEvent,
}

DOC_TYPES = {
    "article": {
        "label": "Article",
        "class": Article,
    },
    "press-release": {
        "label": "Communiqué de presse",
        "class": Article,
    },
    "press-event": {
        "label": "Evénement de presse",
        "class": Article,
    },
    "public-event": {
        "label": "Evénement public",
        "class": Article,
    },
    "training-event": {
        "label": "Formation",
        "class": Article,
    },
    "editorial-product": {
        "label": "Produit éditorial",
        "class": Article,
    },
    "image": {
        "label": "Image",
        "class": Article,
    },
    "video": {
        "label": "Vidéo",
        "class": Article,
    },
    "pitch": {
        "label": "Proposition de sujet",
        "class": Article,
    },
    "mission": {
        "label": "Proposition de mission",
        "class": Article,
    },
    "call-for-witnesses": {
        "label": "Avis d'enquête",
        "class": Article,
    },
}
