# Copyright (c) 2021-2024 - Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

import json
import random
from pathlib import Path
from typing import Any

STOP_WORDS = [
    "colspan",
    "rowspan",
    "font-size",
    "font-family",
    "font-weight",
    "__NOEDITSECTION__",
    "style",
    "DynamicPageList",
    "thumb|",
    "vignette|",
    "|right",
    "Invalid line:",
    "|thumbs",
]


def random_wikinews_article() -> dict[str, Any]:
    files = list(Path("data/news").glob("*.json"))
    while True:
        with random.choice(files).open() as fd:
            doc = json.load(fd)

        return doc

        # if validate_doc(doc):
        #     doc["html"] = doc["html"].replace("<p> Sources </p>", "")
        #     return doc


def validate_doc(doc: dict[str, Any]) -> bool:
    return all(word not in doc["html"] for word in STOP_WORDS)
