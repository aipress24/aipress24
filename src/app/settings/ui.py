"""UI configuration settings for social links and menus."""

# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only
from __future__ import annotations

SOCIAL_LINKS = [
    {
        "name": "GitHub",
        "icon": "github",
        "url": "https://github.com/aipress24    ",
    },
    {
        "name": "LinkedIn",
        "icon": "linkedin",
        "url": "https://www.linkedin.com/company/aipress24",
    },
]

FOOTER_MENU = [
    {
        "label": "Notre offre",
        "items": [
            {
                "label": "Pour les journalistes",
                "url": "/page/offre-journalistes/",
            },
            {
                "label": "Pour les communicants",
                "url": "/page/offre-communicants/",
            },
            {
                "label": "Pour les experts",
                "url": "/page/offre-experts/",
            },
            {
                "label": "Pour les entreprises",
                "url": "/page/offre-entreprises/",
            },
        ],
    },
    {
        "label": "Documentation",
        "items": [
            {
                "label": "Guide utlisateur",
                "url": "https://doc.aipress24.com/user/fr/",
            },
            {
                "label": "Politique de confidentialité",
                "url": "/page/confidentialite/",
            },
            {
                "label": "Conditions d'utilisation",
                "url": "/page/conditions/",
            },
        ],
    },
    {
        "label": "Société",
        "items": [
            {
                "label": "Qui sommes-nous?",
                "url": "/page/a-propos/",
            },
            {
                "label": "Ils nous soutiennent",
                "url": "/page/soutiens/",
            },
            {
                "label": "Contact",
                "url": "/page/contact",
            },
        ],
    },
]
