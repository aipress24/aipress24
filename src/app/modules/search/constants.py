# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from typing import Any

from app.models.auth import User
from app.models.organisation import Organisation
from app.modules.swork.models import Group
from app.modules.wire.models import ArticlePost, PressReleasePost

COLLECTIONS: list[dict[str, Any]] = [
    {
        "name": "all",
        "label": "Tout",
        "icon": "rectangle-stack",
        "class": None,
    },
    {
        "name": "articles",
        "label": "Articles",
        "icon": "newspaper",
        "class": ArticlePost,
    },
    {
        "name": "press-releases",
        "label": "Communiqués",
        "icon": "speaker-wave",
        "class": PressReleasePost,
    },
    # TODO
    # {
    #     "name": "events",
    #     "label": "Evénements",
    #     "icon": "calendar",
    #     "class": Event,
    # },
    {
        "name": "members",
        "label": "Membres",
        "icon": "user",
        "class": User,
    },
    {
        "name": "orgs",
        "label": "Entreprises",
        "icon": "building-office",
        "class": Organisation,
    },
    {
        "name": "groups",
        "label": "Groupes",
        "icon": "user-group",
        "class": Group,
    },
]
