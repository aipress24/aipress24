# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Shared constants and helpers for biz views."""

from __future__ import annotations

TABS = [
    {
        "id": "stories",
        "label": "©",  # ex: "Stories"
        "tip": "",
    },
    {
        "id": "subscriptions",
        "label": "Abonnements",
        "tip": "",
    },
    {
        "id": "missions",
        "label": "Missions",
        "tip": "",
    },
    {
        "id": "projects",
        "label": "Projets",
        "tip": "",
    },
    {
        "id": "jobs",
        "label": "Job Board",
        "tip": "",
    },
]

FILTER_SPECS = [
    {
        "id": "sector",
        "label": "Secteur",
        "selector": "sector",
    },
    {
        "id": "topic",
        "label": "Thématique",
        "selector": "topic",
    },
    {
        "id": "genre",
        "label": "Genre",
        "selector": "genre",
    },
    {
        "id": "location",
        "label": "Localisation",
        "options": ["France", "Europe", "USA", "Chine", "..."],
    },
    {
        "id": "language",
        "label": "Langue",
        "selector": "language",
    },
]
