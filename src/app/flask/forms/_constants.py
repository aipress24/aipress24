# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

import app.settings.vocabularies as voc

__all__ = ["get_choices"]


def get_choices(key: str):
    match key:
        case "genre":
            return voc.get_genres()
        case "genre-com":
            return voc.get_genres_com()
        case "sector":
            return voc.get_news_sectors()
        case "topic":
            return voc.get_topics()
        case "section":
            return voc.get_sections()
        case "language":
            return voc.LANGUAGES
        case "copyright-mention":
            return voc.COPYRIGHT_MENTIONS
        case _:
            msg = f"Invalid key: {key}"
            raise ValueError(msg)
