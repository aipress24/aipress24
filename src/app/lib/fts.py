# Copyright (c) 2021-2024 - Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

import re
import unicodedata

from .html import remove_markup


def unicode_to_ascii(s: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn"
    )


def tokenize(s: str) -> list[str]:
    s = s.strip()
    s = remove_markup(s)
    s = s.lower()
    words = re.split(r"\W+", s)
    s = " ".join(words)
    s = "".join(
        c
        for c in unicodedata.normalize("NFD", s)
        if unicodedata.category(c) in {"Ll", "Nd", "Zs"}
    )
    words = re.split(r"\W+", s)
    return [w for w in words if w]
