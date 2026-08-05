# Copyright (c) 2025, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only
"""Marshmallow schemas and HATEOAS link helpers for the public API.

Serialization is **allowlist-only**: every schema declares exactly the
fields it exposes, so a new model column never leaks automatically. All
PII (emails, phone numbers, billing/Stripe data, raw KYC blobs, owner and
internal FKs, login/IP metadata) is redacted by omission.
"""

from __future__ import annotations

from typing import Any

from flask import current_app, g
from marshmallow import Schema, fields

API_PREFIX = "/api/v1"


# --- HATEOAS link helpers -------------------------------------------------


def link(href: str) -> dict[str, str]:
    return {"href": href}


def collection_path(collection: str) -> str:
    return f"{API_PREFIX}/{collection}"


def resource_path(collection: str, identifier: Any) -> str:
    return f"{API_PREFIX}/{collection}/{identifier}"


def page_links(
    collection: str, limit: int, offset: int, total: int
) -> dict[str, dict[str, str]]:
    """Build self/first/prev/next links for an offset-paginated collection."""
    base = collection_path(collection)

    def page(off: int) -> dict[str, str]:
        return link(f"{base}?limit={limit}&offset={max(off, 0)}")

    links = {"self": page(offset), "first": page(0)}
    if offset > 0:
        links["prev"] = page(offset - limit)
    if offset + limit < total:
        links["next"] = page(offset + limit)
    return links


# --- custom fields --------------------------------------------------------


class IsoDateTime(fields.Field):
    """Serialize a ``datetime`` or ``arrow.Arrow`` as an ISO-8601 string."""

    def _serialize(self, value, attr, obj, **kwargs) -> str | None:
        if not value:
            return None
        return value.isoformat()


class EnumValue(fields.Field):
    """Serialize an enum member as its ``.value`` (or ``None``)."""

    def _serialize(self, value, attr, obj, **kwargs):
        if value is None:
            return None
        return getattr(value, "value", value)


class LinkSchema(Schema):
    href = fields.Str(required=True)


# --- collection envelope --------------------------------------------------


class _CollectionBase(Schema):
    total = fields.Int(metadata={"description": "Total matching resources."})
    count = fields.Int(metadata={"description": "Resources on this page."})
    limit = fields.Int()
    offset = fields.Int()
    links = fields.Dict(data_key="_links")


def make_collection_schema(item_schema_cls: type[Schema]) -> type[Schema]:
    """Build a `{items, total, _links, …}` envelope schema for a resource."""
    name = item_schema_cls.__name__.removesuffix("Schema") + "Collection"
    return type(
        name,
        (_CollectionBase,),
        {"items": fields.List(fields.Nested(item_schema_cls))},
    )


# --- news content (articles & press releases) -----------------------------


class _NewsItemSchema(Schema):
    id = fields.Int()
    title = fields.Str()
    summary = fields.Str()
    content = fields.Method(
        "_content",
        metadata={
            "description": "Sanitized HTML body. For a for-sale item this is "
            "the preview unless the token's user is entitled to the full text."
        },
    )
    genre = fields.Str()
    section = fields.Str()
    topic = fields.Str()
    sector = fields.Str()
    language = fields.Str()
    geo_localisation = fields.Str()
    pays_zip_ville = fields.Str()
    published_at = IsoDateTime()
    last_updated_at = IsoDateTime()
    expires_at = IsoDateTime()
    view_count = fields.Int()
    like_count = fields.Int()
    comment_count = fields.Int()
    publisher_id = fields.Int(allow_none=True)
    media_id = fields.Int(allow_none=True)
    links = fields.Method("_make_links", data_key="_links")

    _collection = ""  # overridden per concrete schema

    def _content(self, obj) -> str:
        """Return the full body only to an entitled token-user, else a preview.

        Mirrors the site's paywall (`wire/views/item.py`): the author, an
        admin, or a paid/gifted-consultation holder sees the full text; anyone
        else sees `truncate_body(...)`. When the paywall is not live the site
        shows the full body to everyone, so we do too — access parity with the
        UI. The entitlement decision is the domain's, not re-implemented here.

        Note: on list endpoints this runs the entitlement check per item; if
        that ever bites, drop `content` from the collection schema (list =
        summaries) or batch the purchase lookup.
        """
        # Local import avoids a load-order cycle during app bootstrap
        # (schemas is imported while wire is still loading); mirrors item.py.
        from app.modules.wire.services.article_access import (
            truncate_body,
            user_can_read_full,
        )

        body = obj.content or ""
        if not current_app.config.get("STRIPE_LIVE_ENABLED"):
            return body
        if user_can_read_full(g.get("api_identity"), obj):
            return body
        return truncate_body(body)

    def _make_links(self, obj) -> dict[str, dict[str, str]]:
        links = {"self": link(resource_path(self._collection, obj.id))}
        if obj.publisher_id:
            links["publisher"] = link(resource_path("organisations", obj.publisher_id))
        if obj.media_id:
            links["media"] = link(resource_path("organisations", obj.media_id))
        return links


class ArticleSchema(_NewsItemSchema):
    kind = fields.Constant("article")
    _collection = "articles"


class PressReleaseSchema(_NewsItemSchema):
    kind = fields.Constant("press_release")
    _collection = "press-releases"


# --- events ---------------------------------------------------------------


class EventSchema(Schema):
    id = fields.Int()
    kind = fields.Constant("event")
    title = fields.Str()
    summary = fields.Str()
    content = fields.Str()
    start_datetime = IsoDateTime()
    end_datetime = IsoDateTime()
    genre = fields.Str()
    category = fields.Str()
    sector = fields.Str()
    language = fields.Str()
    location = fields.Str()
    logo_url = fields.Str()
    cover_image_url = fields.Str()
    city = fields.Str()
    region = fields.Str()
    country = fields.Str()
    zip_code = fields.Str()
    geo_lat = fields.Float()
    geo_lng = fields.Float()
    links = fields.Method("_make_links", data_key="_links")

    def _make_links(self, obj) -> dict[str, dict[str, str]]:
        return {"self": link(resource_path("events", obj.id))}


# --- organisations --------------------------------------------------------


class OrganisationSchema(Schema):
    id = fields.Int()
    name = fields.Str()
    slug = fields.Str()
    status = fields.Str()
    karma = fields.Int()
    bw_active = fields.Str(allow_none=True)
    bw_name = fields.Str()
    city = fields.Str()
    region = fields.Str()
    country = fields.Str()
    zip_code = fields.Str()
    geo_lat = fields.Float()
    geo_lng = fields.Float()
    links = fields.Method("_make_links", data_key="_links")

    def _make_links(self, obj) -> dict[str, dict[str, str]]:
        links = {"self": link(resource_path("organisations", obj.id))}
        if obj.bw_id:
            links["business_wall"] = link(resource_path("business-walls", obj.bw_id))
        return links


# --- business walls -------------------------------------------------------


class BusinessWallSchema(Schema):
    id = fields.Str()
    bw_type = fields.Str()
    status = fields.Str()
    name = fields.Str()
    name_official = fields.Str()
    name_group = fields.Str()
    name_institution = fields.Str()
    positionnement_editorial = fields.Str()
    presentation = fields.Str()
    audience_cible = fields.Str()
    periodicite = fields.Str()
    site_url = fields.Str()
    type_organisation = fields.List(fields.Str())
    secteurs_activite = fields.List(fields.Str())
    logo_url = fields.Method("_logo_url")
    cover_url = fields.Method("_cover_url")
    organisation_id = fields.Int(allow_none=True)
    links = fields.Method("_make_links", data_key="_links")

    def _signed(self, method_name: str, obj) -> str | None:
        method = getattr(obj, method_name, None)
        if method is None:
            return None
        try:
            return method()
        except Exception:
            return None

    def _logo_url(self, obj) -> str | None:
        return self._signed("logo_image_signed_url", obj)

    def _cover_url(self, obj) -> str | None:
        return self._signed("cover_image_signed_url", obj)

    def _make_links(self, obj) -> dict[str, dict[str, str]]:
        links = {"self": link(resource_path("business-walls", obj.id))}
        if obj.organisation_id:
            links["organisation"] = link(
                resource_path("organisations", obj.organisation_id)
            )
        return links


# --- members (curated public profiles) ------------------------------------


class MemberSchema(Schema):
    id = fields.Int()
    first_name = fields.Str()
    last_name = fields.Str()
    full_name = fields.Str()
    gender = fields.Str()
    status = fields.Str()
    karma = fields.Float()
    job_title = fields.Str()
    organisation_name = fields.Str()
    organisation_id = fields.Int(allow_none=True)
    photo_url = fields.Method("_photo_url")
    presentation = fields.Method("_presentation")
    metiers = fields.Method("_metiers")
    competences = fields.Method("_competences")
    langues = fields.Method("_langues")
    secteurs_activite = fields.Method("_secteurs")
    profile_label = fields.Method("_profile_label")
    profile_community = fields.Method("_profile_community")
    links = fields.Method("_make_links", data_key="_links")

    def _photo_url(self, obj) -> str | None:
        try:
            return obj.photo_image_signed_url()
        except Exception:
            return None

    def _profile_attr(self, obj, name: str, default):
        profile = getattr(obj, "profile", None)
        if profile is None:
            return default
        return getattr(profile, name, default)

    def _presentation(self, obj) -> str:
        return self._profile_attr(obj, "presentation", "")

    def _metiers(self, obj) -> list[str]:
        return self._profile_attr(obj, "metiers", [])

    def _competences(self, obj) -> list[str]:
        return self._profile_attr(obj, "competences", [])

    def _langues(self, obj) -> list[str]:
        return self._profile_attr(obj, "langues", [])

    def _secteurs(self, obj) -> list[str]:
        return self._profile_attr(obj, "secteurs_activite", [])

    def _profile_label(self, obj) -> str:
        return self._profile_attr(obj, "profile_label", "")

    def _profile_community(self, obj) -> str:
        return self._profile_attr(obj, "profile_community", "")

    def _make_links(self, obj) -> dict[str, dict[str, str]]:
        links = {"self": link(resource_path("members", obj.id))}
        if obj.organisation_id:
            links["organisation"] = link(
                resource_path("organisations", obj.organisation_id)
            )
        return links


# --- owner-scoped (/me) self profile -------------------------------------


class SelfProfileSchema(Schema):
    """The token owner's own profile — fuller than the public member card.

    Adds the owner's own contact details and account state (which the public
    card redacts), but never account secrets (``password``, ``fs_uniquifier``),
    clone plumbing, login/IP metadata, or raw KYC blobs.
    """

    id = fields.Int()
    email = fields.Str()
    email_secours = fields.Str(allow_none=True)
    first_name = fields.Str()
    last_name = fields.Str()
    full_name = fields.Str()
    gender = fields.Str()
    tel_mobile = fields.Str()
    status = fields.Str()
    karma = fields.Float()
    validation_status = fields.Str()
    validated_at = IsoDateTime()
    created_at = IsoDateTime()
    modified_at = IsoDateTime()
    gcu_acceptation = fields.Bool()
    job_title = fields.Str()
    organisation_name = fields.Str()
    organisation_id = fields.Int(allow_none=True)
    roles = fields.Method("_roles")
    profile_community = fields.Method("_profile_community")
    profile_label = fields.Method("_profile_label")
    presentation = fields.Method("_presentation")
    metiers = fields.Method("_metiers")
    competences = fields.Method("_competences")
    langues = fields.Method("_langues")
    secteurs_activite = fields.Method("_secteurs")
    photo_url = fields.Method("_photo_url")
    cover_url = fields.Method("_cover_url")
    links = fields.Method("_make_links", data_key="_links")

    def _roles(self, obj) -> list[str]:
        return [role.name for role in obj.roles]

    def _profile_attr(self, obj, name: str, default):
        profile = getattr(obj, "profile", None)
        if profile is None:
            return default
        return getattr(profile, name, default)

    def _profile_community(self, obj) -> str:
        return self._profile_attr(obj, "profile_community", "")

    def _profile_label(self, obj) -> str:
        return self._profile_attr(obj, "profile_label", "")

    def _presentation(self, obj) -> str:
        return self._profile_attr(obj, "presentation", "")

    def _metiers(self, obj) -> list[str]:
        return self._profile_attr(obj, "metiers", [])

    def _competences(self, obj) -> list[str]:
        return self._profile_attr(obj, "competences", [])

    def _langues(self, obj) -> list[str]:
        return self._profile_attr(obj, "langues", [])

    def _secteurs(self, obj) -> list[str]:
        return self._profile_attr(obj, "secteurs_activite", [])

    def _signed(self, obj, method_name: str) -> str | None:
        method = getattr(obj, method_name, None)
        if method is None:
            return None
        try:
            return method()
        except Exception:
            return None

    def _photo_url(self, obj) -> str | None:
        return self._signed(obj, "photo_image_signed_url")

    def _cover_url(self, obj) -> str | None:
        return self._signed(obj, "cover_image_signed_url")

    def _make_links(self, obj) -> dict[str, dict[str, str]]:
        links = {"self": link(f"{API_PREFIX}/me")}
        # The token owner is active + non-clone (tokens are refused otherwise),
        # so they are also listable in the public directory.
        links["public_profile"] = link(resource_path("members", obj.id))
        if obj.organisation_id:
            links["organisation"] = link(
                resource_path("organisations", obj.organisation_id)
            )
        return links


# --- owner-scoped (/me) newsroom content & enquiry notices -----------------
# These serialize the user's own SOURCE records (any status, incl. drafts) —
# not the public wire mirror — so the body is never truncated.


class _MyNewsroomSchema(Schema):
    id = fields.Int()
    titre = fields.Str()
    chapo = fields.Str()
    contenu = fields.Str()
    genre = fields.Str()
    section = fields.Str()
    topic = fields.Str()
    sector = fields.Str()
    geo_localisation = fields.Str()
    language = fields.Str()
    status = fields.Str()
    address = fields.Str()
    pays_zip_ville = fields.Str()
    published_at = IsoDateTime()
    expired_at = IsoDateTime()
    created_at = IsoDateTime()
    modified_at = IsoDateTime()
    publisher_id = fields.Int(allow_none=True)
    links = fields.Method("_make_links", data_key="_links")

    _collection = ""

    def _make_links(self, obj) -> dict[str, dict[str, str]]:
        return {"self": link(resource_path(self._collection, obj.id))}


class MyArticleSchema(_MyNewsroomSchema):
    kind = fields.Constant("article")
    brief = fields.Str()
    copyright = fields.Str()
    media_id = fields.Int(allow_none=True)
    commanditaire_id = fields.Int(allow_none=True)
    date_parution_prevue = IsoDateTime()
    date_publication_aip24 = IsoDateTime()
    _collection = "me/articles"


class MyPressReleaseSchema(_MyNewsroomSchema):
    kind = fields.Constant("press_release")
    embargoed_until = IsoDateTime()
    _collection = "me/press-releases"


class MyEventSchema(Schema):
    """The caller's own **source** Event (any status) — not the public mirror.

    The public :class:`EventSchema` serializes the ``EventPost`` mirror
    (``start_datetime``/``city``/…); this serializes the wip ``Event`` source
    with its own field names (``start_time``/``event_type``/…), so a written
    event round-trips through the same names it was created with.
    """

    id = fields.Int()
    kind = fields.Constant("event")
    titre = fields.Str()
    chapo = fields.Str()
    contenu = fields.Str()
    status = fields.Str()
    event_type = fields.Str()
    sector = fields.Str()
    address = fields.Str()
    pays_zip_ville = fields.Str()
    url = fields.Str()
    language = fields.Str()
    start_time = IsoDateTime()
    end_time = IsoDateTime()
    published_at = IsoDateTime()
    expired_at = IsoDateTime()
    publisher_id = fields.Int(allow_none=True)
    created_at = IsoDateTime()
    modified_at = IsoDateTime()
    links = fields.Method("_make_links", data_key="_links")

    def _make_links(self, obj) -> dict[str, dict[str, str]]:
        return {"self": link(resource_path("me/events", obj.id))}


class MyAvisEnqueteSchema(Schema):
    id = fields.Int()
    kind = fields.Constant("avis_enquete")
    type_avis = fields.Str()
    status = fields.Str()
    titre = fields.Str()
    brief = fields.Str()
    contenu = fields.Str()
    genre = fields.Str()
    section = fields.Str()
    topic = fields.Str()
    sector = fields.Str()
    geo_localisation = fields.Str()
    language = fields.Str()
    date_debut_enquete = IsoDateTime()
    date_fin_enquete = IsoDateTime()
    date_bouclage = IsoDateTime()
    date_parution_prevue = IsoDateTime()
    # The journalist's own targeting criteria (not the recipients' PII, which
    # lives in ContactAvisEnquete and is never serialized here).
    ciblage_secteur_detailles = fields.Str()
    ciblage_directions_expertise = fields.Str(allow_none=True)
    ciblage_types_organisation = fields.Str(allow_none=True)
    ciblage_tailles_organisation = fields.Str(allow_none=True)
    ciblage_geolocation = fields.Str(allow_none=True)
    media_id = fields.Int(allow_none=True)
    publisher_id = fields.Int(allow_none=True)
    created_at = IsoDateTime()
    modified_at = IsoDateTime()
    links = fields.Method("_make_links", data_key="_links")

    def _make_links(self, obj) -> dict[str, dict[str, str]]:
        return {"self": link(resource_path("me/enquiry-notices", obj.id))}


# --- owner-scoped (/me) marketplace offers & products ---------------------
# The owner's own marketplace items (any status), so their own contact_email
# is theirs to see. Applications/purchases (third-party PII) are not exposed.


class _MyOfferSchema(Schema):
    id = fields.Int()
    title = fields.Str()
    description = fields.Str()
    location = fields.Str()
    pays_zip_ville = fields.Str()
    currency = fields.Str()
    contact_email = fields.Str()
    emitter_org_id = fields.Int(allow_none=True)
    mission_status = EnumValue()
    status = EnumValue()
    subcategory = fields.Str()
    created_at = IsoDateTime()
    modified_at = IsoDateTime()
    links = fields.Method("_make_links", data_key="_links")

    _collection = ""

    def _make_links(self, obj) -> dict[str, dict[str, str]]:
        return {"self": link(resource_path(self._collection, obj.id))}


class MyMissionSchema(_MyOfferSchema):
    kind = fields.Constant("mission")
    budget_min = fields.Int(allow_none=True)
    budget_max = fields.Int(allow_none=True)
    deadline = IsoDateTime()
    category = EnumValue()
    physical_required = fields.Bool()
    remote_required = fields.Bool()
    metiers_journalisme = fields.List(fields.Str())
    competences_journalisme = fields.List(fields.Str())
    langues = fields.List(fields.Str())
    _collection = "me/missions"


class MyProjectSchema(_MyOfferSchema):
    kind = fields.Constant("project")
    budget_min = fields.Int(allow_none=True)
    budget_max = fields.Int(allow_none=True)
    deadline = IsoDateTime()
    team_size = fields.Int(allow_none=True)
    duration_months = fields.Int(allow_none=True)
    project_category = fields.Str()
    project_type = fields.Str()
    _collection = "me/projects"


class MyJobSchema(_MyOfferSchema):
    kind = fields.Constant("job")
    salary_min = fields.Int(allow_none=True)
    salary_max = fields.Int(allow_none=True)
    starting_date = IsoDateTime()
    contract_type = EnumValue()
    full_time = fields.Bool()
    remote_ok = fields.Bool()
    _collection = "me/jobs"


class MyEditorialProductSchema(Schema):
    id = fields.Int()
    kind = fields.Constant("editorial_product")
    title = fields.Str()
    description = fields.Str()
    image_url = fields.Str()
    product_type = fields.Str()
    price = fields.Int()
    status = EnumValue()
    created_at = IsoDateTime()
    modified_at = IsoDateTime()
    links = fields.Method("_make_links", data_key="_links")

    def _make_links(self, obj) -> dict[str, dict[str, str]]:
        return {"self": link(resource_path("me/products", obj.id))}


# --- write inputs (owner-scoped authoring) --------------------------------


class PressReleaseWriteSchema(Schema):
    """Loadable fields for creating/updating a press release (communiqué).

    Only the author-editable fields are accepted; ``owner``, ``status`` and
    ``published_at`` are set by the domain, never by the caller. ``titre`` is
    required on create; on update the schema is loaded with ``partial=True``
    so any subset may be sent. ``titre``/``chapo``/``contenu`` are sanitized
    server-side (the model only sanitizes ``contenu``). Field names match the
    read schema (:class:`MyPressReleaseSchema`) so payloads round-trip.
    """

    titre = fields.Str(required=True, metadata={"description": "Title (required)."})
    chapo = fields.Str(metadata={"description": "Standfirst / lede."})
    contenu = fields.Str(metadata={"description": "Body (sanitized HTML)."})
    genre = fields.Str()
    section = fields.Str()
    topic = fields.Str()
    sector = fields.Str()
    geo_localisation = fields.Str()
    language = fields.Str()
    address = fields.Str()
    pays_zip_ville = fields.Str()
    publisher_id = fields.Int(
        allow_none=True,
        metadata={
            "description": "Organisation to attribute/publish on behalf of. "
            "Defaults to the caller's own organisation; a client org is only "
            "accepted if the caller is authorized to publish for it."
        },
    )
    embargoed_until = fields.AwareDateTime(
        allow_none=True,
        metadata={"description": "Publication is refused while this is in the future."},
    )


class PressReleaseUpdateSchema(PressReleaseWriteSchema):
    """PATCH variant: every field optional (only the sent keys are applied)."""

    titre = fields.Str(metadata={"description": "Title."})


class ArticleWriteSchema(Schema):
    """Loadable fields for creating/updating a newsroom article.

    Articles are strictly own-organisation: attribution (``media`` /
    ``publisher``) is set server-side to the journalist's own organisation —
    there is no on-behalf ``publisher_id`` input (unlike press releases).
    ``titre`` is required on create. Only ``contenu`` is sanitized (the model
    sanitizes it too); ``titre``/``chapo`` are stored verbatim, as in the UI.
    """

    titre = fields.Str(required=True, metadata={"description": "Title (required)."})
    chapo = fields.Str(metadata={"description": "Standfirst / lede."})
    contenu = fields.Str(metadata={"description": "Body (sanitized HTML)."})
    brief = fields.Str()
    copyright = fields.Str()
    genre = fields.Str()
    section = fields.Str()
    topic = fields.Str()
    sector = fields.Str()
    geo_localisation = fields.Str()
    language = fields.Str()
    address = fields.Str()
    pays_zip_ville = fields.Str()
    date_parution_prevue = fields.AwareDateTime(
        allow_none=True,
        metadata={"description": "Planned publication date (defaults to now)."},
    )


class ArticleUpdateSchema(ArticleWriteSchema):
    """PATCH variant: every field optional."""

    titre = fields.Str(metadata={"description": "Title."})


class EventWriteSchema(Schema):
    """Loadable fields for creating/updating an event.

    Events, like press releases, may be published on behalf of a client
    organisation via ``publisher_id`` (validated against the caller's
    partnerships). ``start_time``/``end_time`` are optional on a draft but
    required to publish (the domain refuses a dateless event).
    """

    titre = fields.Str(required=True, metadata={"description": "Title (required)."})
    chapo = fields.Str(metadata={"description": "Standfirst / lede."})
    contenu = fields.Str(metadata={"description": "Body (sanitized HTML)."})
    event_type = fields.Str()
    sector = fields.Str()
    address = fields.Str()
    pays_zip_ville = fields.Str()
    url = fields.Str()
    language = fields.Str()
    start_time = fields.AwareDateTime(
        allow_none=True, metadata={"description": "Start; required to publish."}
    )
    end_time = fields.AwareDateTime(
        allow_none=True, metadata={"description": "End; required to publish, >= start."}
    )
    publisher_id = fields.Int(
        allow_none=True,
        metadata={
            "description": "Organisation to attribute/publish on behalf of. "
            "Defaults to the caller's own organisation; a client org is only "
            "accepted if the caller is authorized to publish for it."
        },
    )


class EventUpdateSchema(EventWriteSchema):
    """PATCH variant: every field optional."""

    titre = fields.Str(metadata={"description": "Title."})


# --- query arguments & errors ---------------------------------------------


class PageArgsSchema(Schema):
    limit = fields.Int(load_default=20, metadata={"description": "1–100."})
    offset = fields.Int(load_default=0)


class RootSchema(Schema):
    api = fields.Str()
    version = fields.Str()
    links = fields.Dict(data_key="_links")


ArticleCollection = make_collection_schema(ArticleSchema)
PressReleaseCollection = make_collection_schema(PressReleaseSchema)
EventCollection = make_collection_schema(EventSchema)
OrganisationCollection = make_collection_schema(OrganisationSchema)
BusinessWallCollection = make_collection_schema(BusinessWallSchema)
MemberCollection = make_collection_schema(MemberSchema)
MyArticleCollection = make_collection_schema(MyArticleSchema)
MyPressReleaseCollection = make_collection_schema(MyPressReleaseSchema)
MyEventCollection = make_collection_schema(MyEventSchema)
MyAvisEnqueteCollection = make_collection_schema(MyAvisEnqueteSchema)
MyMissionCollection = make_collection_schema(MyMissionSchema)
MyProjectCollection = make_collection_schema(MyProjectSchema)
MyJobCollection = make_collection_schema(MyJobSchema)
MyEditorialProductCollection = make_collection_schema(MyEditorialProductSchema)
