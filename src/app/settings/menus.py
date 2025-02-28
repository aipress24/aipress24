# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

MAIN_MENU = [
    {
        "label": "News",
        "endpoint": "wire.wire",
        "tooltip": "Mon fil d'actu",
    },
    {
        "label": "Work",
        "endpoint": "wip.wip",
        "tooltip": "Mon espace de travail (Work In Progress)",
    },
    {
        "label": "Events",
        "endpoint": "events.events",
        "tooltip": "Evénements",
    },
    {
        "label": "Market",
        "endpoint": "biz.biz",
        "tooltip": "Place de marché",
    },
    {
        "label": "Social",
        "endpoint": "swork.swork",
        "tooltip": "Réseau social professionel",
    },
]

USER_MENU = [
    {
        "label": "Mon profil",
        "endpoint": "swork.profile",
    },
    {
        "label": "Préférences",
        "endpoint": "preferences.home",
    },
    {
        "label": "Performances",
        "endpoint": "wip.performance",
    },
    # TODO
    # {
    #     "label": "Mes achats",
    #     "endpoint": "biz.purchases",
    # },
    {
        "label": "Administration",
        "endpoint": "admin.index",
        "roles": {"admin"},
    },
    {
        "label": "Déconnexion",
        "endpoint": "iam.logout",
    },
]

_CREATE_MENU = [
    #
    # Pour les journalistes
    #
    # {
    #     "label": "Rédiger un article",
    #     "type": "article",
    # },
    # {
    #     "label": "Créer un sujet",
    #     "type": "newsroom:sujet",
    # },
    # {
    #     "label": "Créer un avis d'enquête",
    #     "type": "avis-enquete",
    # },
    # {
    #     "label": "Créer un appel à témoins",
    #     "type": "call-for-witnesses",
    # },
    # {
    #     "label": "Téléverser une image",
    #     "type": "image",
    # },
    #
    # Pour la com'
    #
    # {
    #     "label": "Rédiger un communiqué",
    #     "type": "press-release",
    # },
    # {
    #     "label": "Annoncer un événement presse",
    #     "type": "press-event",
    # },
    # {
    #     "label": "Annoncer un événement public",
    #     "type": "public-event",
    # },
    # {
    #     "label": "Annoncer une formation",
    #     "type": "training-event",
    # },
    #
    # Pour tous
    #
    # {
    #     "label": "Publier une petite annonce",
    #     "type": "#",
    # },
    # {
    #     "label": "Publier un appel d'offres",
    #     "type": "#",
    # },
    # {
    #     "label": "Publier une proposition de partenariat",
    #     "type": "#",
    # },
]

CREATE_MENU = [
    {
        "label": d["label"],
        "endpoint": f"/wip/contents?mode=create&doc_type={d['type']}",
    }
    for d in _CREATE_MENU
]
