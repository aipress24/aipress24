# Copyright (c) 2021-2024 - Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

import re

SLEEP = 0.1
TITLE_RE = re.compile(".* - AIpress24")
NEWS_PATH = "/wire/tab/wall"
CRAWL_LIMIT = 50
ROLES = [
    "journaliste",
    "communicant",
    "expert",
    "transformer",
    "etudiant",
]
ROLE_MAP = {
    "journaliste": "journalist",
    "communicant": "press_relations",
    "expert": "expert",
    "transformer": "transformer",
    "etudiant": "academic",
}
