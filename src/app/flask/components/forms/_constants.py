# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

import app.settings.vocabularies as voc

__all__ = ["get_choices"]


def get_choices():
    return {
        "genre": voc.get_genres(),
        "sector": voc.get_news_sectors(),
        "topic": voc.get_topics(),
        "section": voc.get_sections(),
        "language": voc.LANGUAGES,
        "copyright-mention": voc.COPYRIGHT_MENTIONS,
    }
