# Copyright (c) 2025, Abilian SAS & TCA
#
# SPDX-License-Identifier: Apache-2.0
"""AUTO-GENERATED from the OpenAPI spec by ``generate.py`` — do not edit.

Regenerate with ``make api-sdk``. A unit test asserts this file matches the
served ``/api/v1/openapi.json``.
"""

from __future__ import annotations

from typing import Any, TypedDict


class Article(TypedDict, total=False):
    _links: dict[str, Any]
    comment_count: int
    content: str
    expires_at: str | None
    genre: str
    geo_localisation: str
    id: int
    kind: str
    language: str
    last_updated_at: str | None
    like_count: int
    media_id: int | None
    pays_zip_ville: str
    published_at: str | None
    publisher_id: int | None
    section: str
    sector: str
    summary: str
    title: str
    topic: str
    view_count: int


class ArticleCollection(TypedDict, total=False):
    _links: dict[str, Any]
    count: int
    items: list[Article]
    limit: int
    offset: int
    total: int


class ArticleUpdate(TypedDict, total=False):
    address: str
    brief: str
    chapo: str
    contenu: str
    copyright: str
    date_parution_prevue: str | None
    genre: str
    geo_localisation: str
    language: str
    pays_zip_ville: str
    section: str
    sector: str
    titre: str
    topic: str


class ArticleWrite(TypedDict, total=False):
    address: str
    brief: str
    chapo: str
    contenu: str
    copyright: str
    date_parution_prevue: str | None
    genre: str
    geo_localisation: str
    language: str
    pays_zip_ville: str
    section: str
    sector: str
    titre: str
    topic: str


class BusinessWall(TypedDict, total=False):
    _links: dict[str, Any]
    audience_cible: str
    bw_type: str
    cover_url: str | None
    id: str
    logo_url: str | None
    name: str
    name_group: str
    name_institution: str
    name_official: str
    organisation_id: int | None
    periodicite: str
    positionnement_editorial: str
    presentation: str
    secteurs_activite: list[str]
    site_url: str
    status: str
    type_organisation: list[str]


class BusinessWallCollection(TypedDict, total=False):
    _links: dict[str, Any]
    count: int
    items: list[BusinessWall]
    limit: int
    offset: int
    total: int


class Event(TypedDict, total=False):
    _links: dict[str, Any]
    category: str
    city: str
    content: str
    country: str
    cover_image_url: str
    end_datetime: str | None
    genre: str
    geo_lat: float
    geo_lng: float
    id: int
    kind: str
    language: str
    location: str
    logo_url: str
    mode: str
    platform: str
    region: str
    sector: str
    start_datetime: str | None
    summary: str
    title: str
    zip_code: str


class EventCollection(TypedDict, total=False):
    _links: dict[str, Any]
    count: int
    items: list[Event]
    limit: int
    offset: int
    total: int


class EventUpdate(TypedDict, total=False):
    access_details: str
    address: str
    chapo: str
    contenu: str
    end_time: str | None
    event_type: str
    language: str
    mode: str
    pays_zip_ville: str
    platform: str
    publisher_id: int | None
    sector: str
    start_time: str | None
    titre: str
    url: str


class EventWrite(TypedDict, total=False):
    access_details: str
    address: str
    chapo: str
    contenu: str
    end_time: str | None
    event_type: str
    language: str
    mode: str
    pays_zip_ville: str
    platform: str
    publisher_id: int | None
    sector: str
    start_time: str | None
    titre: str
    url: str


class Member(TypedDict, total=False):
    _links: dict[str, Any]
    competences: list[str]
    first_name: str
    full_name: str
    gender: str
    id: int
    job_title: str
    karma: float
    langues: list[str]
    last_name: str
    metiers: list[str]
    organisation_id: int | None
    organisation_name: str
    photo_url: str | None
    presentation: str
    profile_community: str
    profile_label: str
    secteurs_activite: list[str]
    status: str


class MemberCollection(TypedDict, total=False):
    _links: dict[str, Any]
    count: int
    items: list[Member]
    limit: int
    offset: int
    total: int


class MyArticle(TypedDict, total=False):
    _links: dict[str, Any]
    address: str
    brief: str
    chapo: str
    commanditaire_id: int | None
    contenu: str
    copyright: str
    created_at: str | None
    date_parution_prevue: str | None
    date_publication_aip24: str | None
    expired_at: str | None
    genre: str
    geo_localisation: str
    id: int
    kind: str
    language: str
    media_id: int | None
    modified_at: str | None
    pays_zip_ville: str
    published_at: str | None
    publisher_id: int | None
    section: str
    sector: str
    status: str
    titre: str
    topic: str


class MyArticleCollection(TypedDict, total=False):
    _links: dict[str, Any]
    count: int
    items: list[MyArticle]
    limit: int
    offset: int
    total: int


class MyAvisEnquete(TypedDict, total=False):
    _links: dict[str, Any]
    brief: str
    ciblage_directions_expertise: str | None
    ciblage_geolocation: str | None
    ciblage_secteur_detailles: str
    ciblage_tailles_organisation: str | None
    ciblage_types_organisation: str | None
    contenu: str
    created_at: str | None
    date_bouclage: str | None
    date_debut_enquete: str | None
    date_fin_enquete: str | None
    date_parution_prevue: str | None
    genre: str
    geo_localisation: str
    id: int
    kind: str
    language: str
    media_id: int | None
    modified_at: str | None
    publisher_id: int | None
    section: str
    sector: str
    status: str
    titre: str
    topic: str
    type_avis: str


class MyAvisEnqueteCollection(TypedDict, total=False):
    _links: dict[str, Any]
    count: int
    items: list[MyAvisEnquete]
    limit: int
    offset: int
    total: int


class MyEditorialProduct(TypedDict, total=False):
    _links: dict[str, Any]
    created_at: str | None
    description: str
    id: int
    image_url: str
    kind: str
    modified_at: str | None
    price: int
    product_type: str
    status: str | None
    title: str


class MyEditorialProductCollection(TypedDict, total=False):
    _links: dict[str, Any]
    count: int
    items: list[MyEditorialProduct]
    limit: int
    offset: int
    total: int


class MyEvent(TypedDict, total=False):
    _links: dict[str, Any]
    access_details: str
    address: str
    chapo: str
    contenu: str
    created_at: str | None
    end_time: str | None
    event_type: str
    expired_at: str | None
    id: int
    kind: str
    language: str
    mode: str
    modified_at: str | None
    pays_zip_ville: str
    platform: str
    published_at: str | None
    publisher_id: int | None
    sector: str
    start_time: str | None
    status: str
    titre: str
    url: str


class MyEventCollection(TypedDict, total=False):
    _links: dict[str, Any]
    count: int
    items: list[MyEvent]
    limit: int
    offset: int
    total: int


class MyJob(TypedDict, total=False):
    _links: dict[str, Any]
    contact_email: str
    contract_type: str | None
    created_at: str | None
    currency: str
    description: str
    emitter_org_id: int | None
    full_time: bool
    id: int
    kind: str
    location: str
    mission_status: str | None
    modified_at: str | None
    pays_zip_ville: str
    remote_ok: bool
    salary_max: int | None
    salary_min: int | None
    starting_date: str | None
    status: str | None
    subcategory: str
    title: str


class MyJobCollection(TypedDict, total=False):
    _links: dict[str, Any]
    count: int
    items: list[MyJob]
    limit: int
    offset: int
    total: int


class MyMission(TypedDict, total=False):
    _links: dict[str, Any]
    budget_max: int | None
    budget_min: int | None
    category: str | None
    competences_journalisme: list[str]
    contact_email: str
    created_at: str | None
    currency: str
    deadline: str | None
    description: str
    emitter_org_id: int | None
    id: int
    kind: str
    langues: list[str]
    location: str
    metiers_journalisme: list[str]
    mission_status: str | None
    modified_at: str | None
    pays_zip_ville: str
    physical_required: bool
    remote_required: bool
    status: str | None
    subcategory: str
    title: str


class MyMissionCollection(TypedDict, total=False):
    _links: dict[str, Any]
    count: int
    items: list[MyMission]
    limit: int
    offset: int
    total: int


class MyPressRelease(TypedDict, total=False):
    _links: dict[str, Any]
    address: str
    chapo: str
    contenu: str
    created_at: str | None
    embargoed_until: str | None
    expired_at: str | None
    genre: str
    geo_localisation: str
    id: int
    kind: str
    language: str
    modified_at: str | None
    pays_zip_ville: str
    pays_zip_ville_detail: str
    published_at: str | None
    publisher_id: int | None
    section: str
    sector: str
    status: str
    titre: str
    topic: str


class MyPressReleaseCollection(TypedDict, total=False):
    _links: dict[str, Any]
    count: int
    items: list[MyPressRelease]
    limit: int
    offset: int
    total: int


class MyProject(TypedDict, total=False):
    _links: dict[str, Any]
    budget_max: int | None
    budget_min: int | None
    contact_email: str
    created_at: str | None
    currency: str
    deadline: str | None
    description: str
    duration_months: int | None
    emitter_org_id: int | None
    id: int
    kind: str
    location: str
    mission_status: str | None
    modified_at: str | None
    pays_zip_ville: str
    project_category: str
    project_type: str
    status: str | None
    subcategory: str
    team_size: int | None
    title: str


class MyProjectCollection(TypedDict, total=False):
    _links: dict[str, Any]
    count: int
    items: list[MyProject]
    limit: int
    offset: int
    total: int


class Organisation(TypedDict, total=False):
    _links: dict[str, Any]
    bw_active: str | None
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


class OrganisationCollection(TypedDict, total=False):
    _links: dict[str, Any]
    count: int
    items: list[Organisation]
    limit: int
    offset: int
    total: int


class PressRelease(TypedDict, total=False):
    _links: dict[str, Any]
    comment_count: int
    content: str
    expires_at: str | None
    genre: str
    geo_localisation: str
    id: int
    kind: str
    language: str
    last_updated_at: str | None
    like_count: int
    media_id: int | None
    pays_zip_ville: str
    published_at: str | None
    publisher_id: int | None
    section: str
    sector: str
    summary: str
    title: str
    topic: str
    view_count: int


class PressReleaseCollection(TypedDict, total=False):
    _links: dict[str, Any]
    count: int
    items: list[PressRelease]
    limit: int
    offset: int
    total: int


class PressReleaseImage(TypedDict, total=False):
    caption: str
    copyright: str
    id: int
    position: int
    sha256: str | None


class PressReleaseImageCollection(TypedDict, total=False):
    items: list[PressReleaseImage]


class PressReleaseUpdate(TypedDict, total=False):
    address: str
    chapo: str
    contenu: str
    embargoed_until: str | None
    genre: str
    geo_localisation: str
    language: str
    pays_zip_ville: str
    pays_zip_ville_detail: str
    publisher_id: int | None
    section: str
    sector: str
    titre: str
    topic: str


class PressReleaseVocabularies(TypedDict, total=False):
    genre: list[str]
    section: list[str]
    sector: list[str]
    topic: list[str]


class PressReleaseWrite(TypedDict, total=False):
    address: str
    chapo: str
    contenu: str
    embargoed_until: str | None
    genre: str
    geo_localisation: str
    language: str
    pays_zip_ville: str
    pays_zip_ville_detail: str
    publisher_id: int | None
    section: str
    sector: str
    titre: str
    topic: str


class Root(TypedDict, total=False):
    _links: dict[str, Any]
    api: str
    version: str


class SelfProfile(TypedDict, total=False):
    _links: dict[str, Any]
    competences: list[str]
    cover_url: str | None
    created_at: str | None
    email: str
    email_secours: str | None
    first_name: str
    full_name: str
    gcu_acceptation: bool
    gender: str
    id: int
    job_title: str
    karma: float
    langues: list[str]
    last_name: str
    metiers: list[str]
    modified_at: str | None
    organisation_id: int | None
    organisation_name: str
    photo_url: str | None
    presentation: str
    profile_community: str
    profile_label: str
    roles: list[str]
    secteurs_activite: list[str]
    status: str
    tel_mobile: str
    validated_at: str | None
    validation_status: str


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
