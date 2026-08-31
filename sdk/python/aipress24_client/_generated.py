# Copyright (c) 2025, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only
"""AUTO-GENERATED from the OpenAPI spec by ``generate.py`` — do not edit.

Regenerate with ``make api-sdk``. A unit test asserts this file matches the
served ``/api/v1/openapi.json``.
"""

from __future__ import annotations

from typing import Any, TypedDict


class Article(TypedDict, total=False):
    _links: Any
    comment_count: int
    content: Any
    expires_at: Any
    genre: str
    geo_localisation: str
    id: int
    kind: Any
    language: str
    last_updated_at: Any
    like_count: int
    media_id: int
    pays_zip_ville: str
    published_at: Any
    publisher_id: int
    section: str
    sector: str
    summary: str
    title: str
    topic: str
    view_count: int


class BusinessWall(TypedDict, total=False):
    _links: Any
    audience_cible: str
    bw_type: str
    cover_url: Any
    id: str
    logo_url: Any
    name: str
    name_group: str
    name_institution: str
    name_official: str
    organisation_id: int
    periodicite: str
    positionnement_editorial: str
    presentation: str
    secteurs_activite: list[str]
    site_url: str
    status: str
    type_organisation: list[str]


class Event(TypedDict, total=False):
    _links: Any
    category: str
    city: str
    content: str
    country: str
    cover_image_url: str
    end_datetime: Any
    genre: str
    geo_lat: float
    geo_lng: float
    id: int
    kind: Any
    language: str
    location: str
    logo_url: str
    mode: str
    platform: str
    region: str
    sector: str
    start_datetime: Any
    summary: str
    title: str
    zip_code: str


class Member(TypedDict, total=False):
    _links: Any
    competences: Any
    first_name: str
    full_name: str
    gender: str
    id: int
    job_title: str
    karma: float
    langues: Any
    last_name: str
    metiers: Any
    organisation_id: int
    organisation_name: str
    photo_url: Any
    presentation: Any
    profile_community: Any
    profile_label: Any
    secteurs_activite: Any
    status: str


class Organisation(TypedDict, total=False):
    _links: Any
    bw_active: str
    bw_name: str
    city: str
    country: str
    geo_lat: float
    geo_lng: float
    id: int
    karma: int
    name: str
    region: str
    slug: str
    status: str
    zip_code: str


class PressRelease(TypedDict, total=False):
    _links: Any
    comment_count: int
    content: Any
    expires_at: Any
    genre: str
    geo_localisation: str
    id: int
    kind: Any
    language: str
    last_updated_at: Any
    like_count: int
    media_id: int
    pays_zip_ville: str
    published_at: Any
    publisher_id: int
    section: str
    sector: str
    summary: str
    title: str
    topic: str
    view_count: int


COLLECTIONS: tuple[str, ...] = (
    "articles",
    "business-walls",
    "events",
    "members",
    "organisations",
    "press-releases",
)


RESOURCE_MODELS: dict[str, type] = {
    "articles": Article,
    "business-walls": BusinessWall,
    "events": Event,
    "members": Member,
    "organisations": Organisation,
    "press-releases": PressRelease,
}
