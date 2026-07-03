# Copyright (c) 2025, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only
"""HTTP resources for the public API.

Each collection requires a capability scope on the caller's token; each
detail lookup 404s on anything outside the public visibility gate (see
:mod:`.queries`). Serialization is delegated to the allowlist schemas.
"""

from __future__ import annotations

from flask.views import MethodView
from flask_smorest import abort

from . import blp, queries as q
from .schemas import (
    API_PREFIX,
    ArticleCollection,
    ArticleSchema,
    BusinessWallCollection,
    BusinessWallSchema,
    EventCollection,
    EventSchema,
    MemberCollection,
    MemberSchema,
    OrganisationCollection,
    OrganisationSchema,
    PageArgsSchema,
    PressReleaseCollection,
    PressReleaseSchema,
    RootSchema,
    collection_path,
    link,
    page_links,
)
from .security import Scope, has_scope


def _require(scope: Scope) -> None:
    if not has_scope(scope):
        abort(403, message=f"This token lacks the required scope: {scope.value}.")


def _collection(name: str, page: q.Page) -> dict:
    rows, total, limit, offset = page
    return {
        "items": rows,
        "total": total,
        "count": len(rows),
        "limit": limit,
        "offset": offset,
        "links": page_links(name, limit, offset, total),
    }


# --- discovery entrypoint (public) ----------------------------------------


@blp.route("/")
@blp.doc(security=[])
@blp.response(200, RootSchema)
def root() -> dict:
    """Entry point: link relations for every collection plus the docs."""
    return {
        "api": "AIpress24 API",
        "version": "1.0",
        "links": {
            "self": link(f"{API_PREFIX}/"),
            "articles": link(collection_path("articles")),
            "press-releases": link(collection_path("press-releases")),
            "events": link(collection_path("events")),
            "organisations": link(collection_path("organisations")),
            "business-walls": link(collection_path("business-walls")),
            "members": link(collection_path("members")),
            "openapi": link(f"{API_PREFIX}/openapi.json"),
            "docs": link(f"{API_PREFIX}/docs"),
        },
    }


# --- articles -------------------------------------------------------------


@blp.route("/articles")
class Articles(MethodView):
    @blp.arguments(PageArgsSchema, location="query")
    @blp.response(200, ArticleCollection)
    def get(self, args: dict) -> dict:
        """List published articles (most recent first)."""
        _require(Scope.READ_CONTENT)
        page = q.list_articles(args["limit"], args["offset"])
        return _collection("articles", page)


@blp.route("/articles/<int:article_id>")
class Article(MethodView):
    @blp.response(200, ArticleSchema)
    def get(self, article_id: int):
        """Fetch a single published article."""
        _require(Scope.READ_CONTENT)
        obj = q.get_article(article_id)
        if obj is None:
            abort(404, message="Article not found.")
        return obj


# --- press releases -------------------------------------------------------


@blp.route("/press-releases")
class PressReleases(MethodView):
    @blp.arguments(PageArgsSchema, location="query")
    @blp.response(200, PressReleaseCollection)
    def get(self, args: dict) -> dict:
        """List published press releases (most recent first)."""
        _require(Scope.READ_CONTENT)
        page = q.list_press_releases(args["limit"], args["offset"])
        return _collection("press-releases", page)


@blp.route("/press-releases/<int:press_release_id>")
class PressRelease(MethodView):
    @blp.response(200, PressReleaseSchema)
    def get(self, press_release_id: int):
        """Fetch a single published press release."""
        _require(Scope.READ_CONTENT)
        obj = q.get_press_release(press_release_id)
        if obj is None:
            abort(404, message="Press release not found.")
        return obj


# --- events ---------------------------------------------------------------


@blp.route("/events")
class Events(MethodView):
    @blp.arguments(PageArgsSchema, location="query")
    @blp.response(200, EventCollection)
    def get(self, args: dict) -> dict:
        """List published events (most recent first)."""
        _require(Scope.READ_CONTENT)
        page = q.list_events(args["limit"], args["offset"])
        return _collection("events", page)


@blp.route("/events/<int:event_id>")
class Event(MethodView):
    @blp.response(200, EventSchema)
    def get(self, event_id: int):
        """Fetch a single published event."""
        _require(Scope.READ_CONTENT)
        obj = q.get_event(event_id)
        if obj is None:
            abort(404, message="Event not found.")
        return obj


# --- organisations --------------------------------------------------------


@blp.route("/organisations")
class Organisations(MethodView):
    @blp.arguments(PageArgsSchema, location="query")
    @blp.response(200, OrganisationCollection)
    def get(self, args: dict) -> dict:
        """List active organisations."""
        _require(Scope.READ_ORGANISATIONS)
        page = q.list_organisations(args["limit"], args["offset"])
        return _collection("organisations", page)


@blp.route("/organisations/<int:organisation_id>")
class Organisation(MethodView):
    @blp.response(200, OrganisationSchema)
    def get(self, organisation_id: int):
        """Fetch a single active organisation."""
        _require(Scope.READ_ORGANISATIONS)
        obj = q.get_organisation(organisation_id)
        if obj is None:
            abort(404, message="Organisation not found.")
        return obj


# --- business walls -------------------------------------------------------


@blp.route("/business-walls")
class BusinessWalls(MethodView):
    @blp.arguments(PageArgsSchema, location="query")
    @blp.response(200, BusinessWallCollection)
    def get(self, args: dict) -> dict:
        """List active Business Walls (public organisation pages)."""
        _require(Scope.READ_ORGANISATIONS)
        page = q.list_business_walls(args["limit"], args["offset"])
        return _collection("business-walls", page)


@blp.route("/business-walls/<uuid:business_wall_id>")
class BusinessWall(MethodView):
    @blp.response(200, BusinessWallSchema)
    def get(self, business_wall_id):
        """Fetch a single active Business Wall."""
        _require(Scope.READ_ORGANISATIONS)
        obj = q.get_business_wall(business_wall_id)
        if obj is None:
            abort(404, message="Business Wall not found.")
        return obj


# --- members --------------------------------------------------------------


@blp.route("/members")
class Members(MethodView):
    @blp.arguments(PageArgsSchema, location="query")
    @blp.response(200, MemberCollection)
    def get(self, args: dict) -> dict:
        """List public member profiles (contact details redacted)."""
        _require(Scope.READ_DIRECTORY)
        page = q.list_members(args["limit"], args["offset"])
        return _collection("members", page)


@blp.route("/members/<int:member_id>")
class Member(MethodView):
    @blp.response(200, MemberSchema)
    def get(self, member_id: int):
        """Fetch a single public member profile."""
        _require(Scope.READ_DIRECTORY)
        obj = q.get_member(member_id)
        if obj is None:
            abort(404, message="Member not found.")
        return obj
