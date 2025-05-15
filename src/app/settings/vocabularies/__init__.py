# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from svcs.flask import container

from app.services.cache import Cache
from app.services.taxonomies import get_taxonomy

__all__ = [
    "get_genres",
    "get_news_sectors",
    "get_sections",
    "get_topics",
]


def get_sections():
    return get_vocab("sections")


def get_news_sectors():
    return get_vocab("news_sectors")


def get_genres():
    return get_vocab("genres")


def get_genres_com():
    return get_vocab("genres-com")


def get_topics():
    return get_vocab("topics")


def get_vocab(name):
    cache = container.get(Cache)
    if name in cache:
        return cache[name]
    value = get_taxonomy(name)
    cache.set(name, value)
    return value


# JOBS = []
# jobs = parse_toml("jobs.toml")
# for k, v in jobs.items():
#     for _kk, vv in v.items():
#         JOBS.append(f"{k} / {vv}")


COPYRIGHT_MENTIONS = [
    "Tous droits réservés",
    "Creative Commons (CC-BY-SA-ND)",
]

PRODUCT_TYPES = [
    "Article",
    "Photo",
    "Illustration",
    "Dataviz",
    "Animation",
    "Vidéo",
    "Son",
    "Podcast",
    "Multimedia",
]

# Not used for now
# def get_all_languages():
#     # ALL_LANGUAGES comes from some library (I don't remember which
#     languages = []
#     for lang in ALL_LANGUAGES:
#         languages.append(lang.name)
#     languages.sort()


# Only latin languages for now
LANGUAGES = [
    "Français",
    "Anglais",
    "Espagnol",
    "Portugais",
    "Allemand",
    "Italien",
    "Albanais",
    "Arménien",
    "Basque",
    "Bosniaque",
    "Breton",
    "Breton",
    "Bulgare",
    "Catalan",
    "Corse",
    "Croate",
    "Danois",
    "Estonien",
    "Finnois",
    "Gallois",
    "Grec",
    "Géorgien",
    "Hongrois",
    "Irlandais",
    "Islandais",
    "Letton",
    "Lituanien",
    "Macédonien",
    "Norvégien",
    "Néerlandais",
    "Polonais",
    "Roumain",
    "Serbe",
    "Slovaque",
    "Slovène",
    "Suédois",
    "Tchèque",
    "Turc",
    "Écossais",
]
