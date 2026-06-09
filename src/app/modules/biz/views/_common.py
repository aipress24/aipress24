# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Shared constants and helpers for biz views."""

from __future__ import annotations

from typing import TypedDict


class FilterSpec(TypedDict, total=False):
    id: str
    label: str
    selector: str
    options: list[str]


class TabSpec(TypedDict, total=False):
    id: str
    label: str
    tip: str
    href: str
    current: bool


TABS: list[TabSpec] = [
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

FILTER_SPECS: list[FilterSpec] = [
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


# Ticket #0202 — extra filters surfaced when the user is browsing
# MARKET / Missions with the JOURNALISME category. Each entry's
# `options` are loaded at request time from the matching KYC ontology
# (`get_ontology_choices(ontology_key)`) — the home view does the
# fetch + flattening. Order chosen to follow Erick's spec list.
class JournalismFilterSpec(TypedDict, total=False):
    id: str
    label: str
    ontology_key: str
    options: list[str]


JOURNALISM_FILTER_SPECS: list[JournalismFilterSpec] = [
    {
        "id": "metiers_journalisme",
        "label": "Métiers du journalisme",
        "ontology_key": "multi_fonctions_journalisme",
    },
    {
        "id": "types_entreprises_presse_medias",
        "label": "Types d'entreprises de presse & médias",
        "ontology_key": "multi_type_entreprise_medias",
    },
    {
        "id": "types_presse_medias",
        "label": "Types presse & médias",
        "ontology_key": "multi_type_media",
    },
    {
        "id": "competences_journalisme",
        "label": "Compétences en journalisme",
        "ontology_key": "multi_competences_journalisme",
    },
    {
        "id": "langues",
        "label": "Langues",
        "ontology_key": "multi_langues",
    },
    {
        "id": "types_contenus_editoriaux",
        "label": "Types de contenus éditoriaux",
        "ontology_key": "multi_type_contenu",
    },
    {
        "id": "modes_remuneration",
        "label": "Modes de rémunération",
        "ontology_key": "multi_mode_remuneration",
    },
    {
        "id": "work_mode",
        "label": "Mode de travail",
        "options": ["Présentiel", "Télétravail"],
    },
    {
        "id": "budget_min",
        "label": "Budget min (€)",
        "options": [],  # free input rendered as <input type=number> by the template
    },
    {
        "id": "budget_max",
        "label": "Budget max (€)",
        "options": [],
    },
    {
        "id": "deadline",
        "label": "Date limite",
        "options": [],
    },
    {
        "id": "pays",
        "label": "Pays",
        "options": [],
    },
    {
        "id": "code_postal_ville",
        "label": "Code postal et ville",
        "options": [],
    },
]
