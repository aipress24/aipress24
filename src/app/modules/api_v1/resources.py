# Copyright (c) 2025, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only
"""HTTP resources for the public API.

Each collection requires a capability scope on the caller's token; each
detail lookup 404s on anything outside the public visibility gate (see
:mod:`.queries`). Serialization is delegated to the allowlist schemas.
"""

from __future__ import annotations

from flask import g
from flask.views import MethodView
from flask_smorest import abort

from . import blp, queries as q, writes as w
from .schemas import (
    API_PREFIX,
    ArticleCollection,
    ArticleSchema,
    ArticleUpdateSchema,
    ArticleWriteSchema,
    BusinessWallCollection,
    BusinessWallSchema,
    EventCollection,
    EventSchema,
    EventUpdateSchema,
    EventWriteSchema,
    MemberCollection,
    MemberSchema,
    MyArticleCollection,
    MyArticleSchema,
    MyAvisEnqueteCollection,
    MyAvisEnqueteSchema,
    MyEditorialProductCollection,
    MyEditorialProductSchema,
    MyEventCollection,
    MyEventSchema,
    MyJobCollection,
    MyJobSchema,
    MyMissionCollection,
    MyMissionSchema,
    MyPressReleaseCollection,
    MyPressReleaseSchema,
    MyProjectCollection,
    MyProjectSchema,
    OrganisationCollection,
    OrganisationSchema,
    PageArgsSchema,
    PressReleaseCollection,
    PressReleaseSchema,
    PressReleaseUpdateSchema,
    PressReleaseWriteSchema,
    RootSchema,
    SelfProfileSchema,
    collection_path,
    link,
    page_links,
)
from .security import Scope, current_identity, has_scope


def _require(scope: Scope) -> None:
    if not has_scope(scope):
        abort(403, message=f"This token lacks the required scope: {scope.value}.")


def _require_write():
    """Enforce ``write:content`` and bind the token user as ``g.user``.

    The reused Com'room authorization predicates and the publish-signal
    receivers read ``flask.g.user``; a token request only carries
    ``g.api_identity``, so we bind it here before any write orchestration.
    """
    _require(Scope.WRITE_CONTENT)
    identity = current_identity()
    g.user = identity
    return identity


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
            "me": link(f"{API_PREFIX}/me"),
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


# --- owner-scoped tier (/me) ----------------------------------------------
# The token identifies the user; these serve only that user's own data
# (any status, incl. drafts). A single-item lookup 404s for a row owned by
# someone else, so ownership never leaks even the existence of a record.


@blp.route("/me")
class Me(MethodView):
    @blp.response(200, SelfProfileSchema)
    def get(self):
        """The authenticated user's own profile (private self-view)."""
        _require(Scope.READ_SELF)
        return current_identity()


@blp.route("/me/articles")
class MyArticles(MethodView):
    @blp.arguments(PageArgsSchema, location="query")
    @blp.response(200, MyArticleCollection)
    def get(self, args: dict) -> dict:
        """List the caller's own newsroom articles (any status)."""
        _require(Scope.READ_SELF)
        page = q.list_my_articles(current_identity().id, args["limit"], args["offset"])
        return _collection("me/articles", page)

    @blp.arguments(ArticleWriteSchema)
    @blp.response(201, MyArticleSchema)
    def post(self, data: dict):
        """Create a newsroom article draft owned by the caller (journalists)."""
        user = _require_write()
        try:
            return w.create_article(user, data)
        except w.WriteError as exc:
            abort(exc.status, message=exc.message)


@blp.route("/me/articles/<int:article_id>")
class MyArticle(MethodView):
    @blp.response(200, MyArticleSchema)
    def get(self, article_id: int):
        """Fetch one of the caller's own articles."""
        _require(Scope.READ_SELF)
        obj = q.get_my_article(current_identity().id, article_id)
        if obj is None:
            abort(404, message="Article not found.")
        return obj

    @blp.arguments(ArticleUpdateSchema)
    @blp.response(200, MyArticleSchema)
    def patch(self, data: dict, article_id: int):
        """Update one of the caller's own articles (partial)."""
        user = _require_write()
        obj = q.get_my_article(user.id, article_id)
        if obj is None:
            abort(404, message="Article not found.")
        try:
            return w.update_article(user, obj, data)
        except w.WriteError as exc:
            abort(exc.status, message=exc.message)

    @blp.response(204)
    def delete(self, article_id: int):
        """Soft-delete one of the caller's own articles."""
        user = _require_write()
        obj = q.get_my_article(user.id, article_id)
        if obj is None:
            abort(404, message="Article not found.")
        try:
            w.delete_article(user, obj)
        except w.WriteError as exc:
            abort(exc.status, message=exc.message)
        return ""


@blp.route("/me/articles/<int:article_id>/publish")
class MyArticlePublish(MethodView):
    @blp.response(200, MyArticleSchema)
    def post(self, article_id: int):
        """Publish one of the caller's own articles."""
        user = _require_write()
        obj = q.get_my_article(user.id, article_id)
        if obj is None:
            abort(404, message="Article not found.")
        try:
            return w.publish_article(user, obj)
        except w.WriteError as exc:
            abort(exc.status, message=exc.message)


@blp.route("/me/articles/<int:article_id>/unpublish")
class MyArticleUnpublish(MethodView):
    @blp.response(200, MyArticleSchema)
    def post(self, article_id: int):
        """Return one of the caller's own articles to draft."""
        user = _require_write()
        obj = q.get_my_article(user.id, article_id)
        if obj is None:
            abort(404, message="Article not found.")
        try:
            return w.unpublish_article(user, obj)
        except w.WriteError as exc:
            abort(exc.status, message=exc.message)


@blp.route("/me/press-releases")
class MyPressReleases(MethodView):
    @blp.arguments(PageArgsSchema, location="query")
    @blp.response(200, MyPressReleaseCollection)
    def get(self, args: dict) -> dict:
        """List the caller's own press releases (any status)."""
        _require(Scope.READ_SELF)
        page = q.list_my_press_releases(
            current_identity().id, args["limit"], args["offset"]
        )
        return _collection("me/press-releases", page)

    @blp.arguments(PressReleaseWriteSchema)
    @blp.response(201, MyPressReleaseSchema)
    def post(self, data: dict):
        """Create a press release draft owned by the caller."""
        user = _require_write()
        try:
            return w.create_press_release(user, data)
        except w.WriteError as exc:
            abort(exc.status, message=exc.message)


@blp.route("/me/press-releases/<int:press_release_id>")
class MyPressRelease(MethodView):
    @blp.response(200, MyPressReleaseSchema)
    def get(self, press_release_id: int):
        """Fetch one of the caller's own press releases."""
        _require(Scope.READ_SELF)
        obj = q.get_my_press_release(current_identity().id, press_release_id)
        if obj is None:
            abort(404, message="Press release not found.")
        return obj

    @blp.arguments(PressReleaseUpdateSchema)
    @blp.response(200, MyPressReleaseSchema)
    def patch(self, data: dict, press_release_id: int):
        """Update one of the caller's own press releases (partial)."""
        user = _require_write()
        obj = q.get_my_press_release(user.id, press_release_id)
        if obj is None:
            abort(404, message="Press release not found.")
        try:
            return w.update_press_release(user, obj, data)
        except w.WriteError as exc:
            abort(exc.status, message=exc.message)

    @blp.response(204)
    def delete(self, press_release_id: int):
        """Soft-delete one of the caller's own press releases."""
        user = _require_write()
        obj = q.get_my_press_release(user.id, press_release_id)
        if obj is None:
            abort(404, message="Press release not found.")
        try:
            w.delete_press_release(user, obj)
        except w.WriteError as exc:
            abort(exc.status, message=exc.message)
        return ""


@blp.route("/me/press-releases/<int:press_release_id>/publish")
class MyPressReleasePublish(MethodView):
    @blp.response(200, MyPressReleaseSchema)
    def post(self, press_release_id: int):
        """Publish one of the caller's own press releases."""
        user = _require_write()
        obj = q.get_my_press_release(user.id, press_release_id)
        if obj is None:
            abort(404, message="Press release not found.")
        try:
            return w.publish_press_release(user, obj)
        except w.WriteError as exc:
            abort(exc.status, message=exc.message)


@blp.route("/me/press-releases/<int:press_release_id>/unpublish")
class MyPressReleaseUnpublish(MethodView):
    @blp.response(200, MyPressReleaseSchema)
    def post(self, press_release_id: int):
        """Return one of the caller's own press releases to draft."""
        user = _require_write()
        obj = q.get_my_press_release(user.id, press_release_id)
        if obj is None:
            abort(404, message="Press release not found.")
        try:
            return w.unpublish_press_release(user, obj)
        except w.WriteError as exc:
            abort(exc.status, message=exc.message)


# --- owner-scoped events (read + write; source Event, any status) ---------


@blp.route("/me/events")
class MyEvents(MethodView):
    @blp.arguments(PageArgsSchema, location="query")
    @blp.response(200, MyEventCollection)
    def get(self, args: dict) -> dict:
        """List the caller's own events (any status)."""
        _require(Scope.READ_SELF)
        page = q.list_my_events(current_identity().id, args["limit"], args["offset"])
        return _collection("me/events", page)

    @blp.arguments(EventWriteSchema)
    @blp.response(201, MyEventSchema)
    def post(self, data: dict):
        """Create an event draft owned by the caller."""
        user = _require_write()
        try:
            return w.create_event(user, data)
        except w.WriteError as exc:
            abort(exc.status, message=exc.message)


@blp.route("/me/events/<int:event_id>")
class MyEvent(MethodView):
    @blp.response(200, MyEventSchema)
    def get(self, event_id: int):
        """Fetch one of the caller's own events."""
        _require(Scope.READ_SELF)
        obj = q.get_my_event(current_identity().id, event_id)
        if obj is None:
            abort(404, message="Event not found.")
        return obj

    @blp.arguments(EventUpdateSchema)
    @blp.response(200, MyEventSchema)
    def patch(self, data: dict, event_id: int):
        """Update one of the caller's own events (partial)."""
        user = _require_write()
        obj = q.get_my_event(user.id, event_id)
        if obj is None:
            abort(404, message="Event not found.")
        try:
            return w.update_event(user, obj, data)
        except w.WriteError as exc:
            abort(exc.status, message=exc.message)

    @blp.response(204)
    def delete(self, event_id: int):
        """Soft-delete one of the caller's own events."""
        user = _require_write()
        obj = q.get_my_event(user.id, event_id)
        if obj is None:
            abort(404, message="Event not found.")
        try:
            w.delete_event(user, obj)
        except w.WriteError as exc:
            abort(exc.status, message=exc.message)
        return ""


@blp.route("/me/events/<int:event_id>/publish")
class MyEventPublish(MethodView):
    @blp.response(200, MyEventSchema)
    def post(self, event_id: int):
        """Publish one of the caller's own events (requires start/end times)."""
        user = _require_write()
        obj = q.get_my_event(user.id, event_id)
        if obj is None:
            abort(404, message="Event not found.")
        try:
            return w.publish_event(user, obj)
        except w.WriteError as exc:
            abort(exc.status, message=exc.message)


@blp.route("/me/events/<int:event_id>/unpublish")
class MyEventUnpublish(MethodView):
    @blp.response(200, MyEventSchema)
    def post(self, event_id: int):
        """Return one of the caller's own events to draft."""
        user = _require_write()
        obj = q.get_my_event(user.id, event_id)
        if obj is None:
            abort(404, message="Event not found.")
        try:
            return w.unpublish_event(user, obj)
        except w.WriteError as exc:
            abort(exc.status, message=exc.message)


@blp.route("/me/enquiry-notices")
class MyEnquiryNotices(MethodView):
    @blp.arguments(PageArgsSchema, location="query")
    @blp.response(200, MyAvisEnqueteCollection)
    def get(self, args: dict) -> dict:
        """List the caller's own enquiry notices (avis d'enquête)."""
        _require(Scope.READ_SELF)
        page = q.list_my_enquiry_notices(
            current_identity().id, args["limit"], args["offset"]
        )
        return _collection("me/enquiry-notices", page)


@blp.route("/me/enquiry-notices/<int:notice_id>")
class MyEnquiryNotice(MethodView):
    @blp.response(200, MyAvisEnqueteSchema)
    def get(self, notice_id: int):
        """Fetch one of the caller's own enquiry notices."""
        _require(Scope.READ_SELF)
        obj = q.get_my_enquiry_notice(current_identity().id, notice_id)
        if obj is None:
            abort(404, message="Enquiry notice not found.")
        return obj


# --- owner-scoped marketplace (the caller's own offers & products) --------


@blp.route("/me/missions")
class MyMissions(MethodView):
    @blp.arguments(PageArgsSchema, location="query")
    @blp.response(200, MyMissionCollection)
    def get(self, args: dict) -> dict:
        """List the caller's own mission offers (any status)."""
        _require(Scope.READ_SELF)
        page = q.list_my_missions(current_identity().id, args["limit"], args["offset"])
        return _collection("me/missions", page)


@blp.route("/me/missions/<int:mission_id>")
class MyMission(MethodView):
    @blp.response(200, MyMissionSchema)
    def get(self, mission_id: int):
        """Fetch one of the caller's own mission offers."""
        _require(Scope.READ_SELF)
        obj = q.get_my_mission(current_identity().id, mission_id)
        if obj is None:
            abort(404, message="Mission not found.")
        return obj


@blp.route("/me/projects")
class MyProjects(MethodView):
    @blp.arguments(PageArgsSchema, location="query")
    @blp.response(200, MyProjectCollection)
    def get(self, args: dict) -> dict:
        """List the caller's own project offers (any status)."""
        _require(Scope.READ_SELF)
        page = q.list_my_projects(current_identity().id, args["limit"], args["offset"])
        return _collection("me/projects", page)


@blp.route("/me/projects/<int:project_id>")
class MyProject(MethodView):
    @blp.response(200, MyProjectSchema)
    def get(self, project_id: int):
        """Fetch one of the caller's own project offers."""
        _require(Scope.READ_SELF)
        obj = q.get_my_project(current_identity().id, project_id)
        if obj is None:
            abort(404, message="Project not found.")
        return obj


@blp.route("/me/jobs")
class MyJobs(MethodView):
    @blp.arguments(PageArgsSchema, location="query")
    @blp.response(200, MyJobCollection)
    def get(self, args: dict) -> dict:
        """List the caller's own job offers (any status)."""
        _require(Scope.READ_SELF)
        page = q.list_my_jobs(current_identity().id, args["limit"], args["offset"])
        return _collection("me/jobs", page)


@blp.route("/me/jobs/<int:job_id>")
class MyJob(MethodView):
    @blp.response(200, MyJobSchema)
    def get(self, job_id: int):
        """Fetch one of the caller's own job offers."""
        _require(Scope.READ_SELF)
        obj = q.get_my_job(current_identity().id, job_id)
        if obj is None:
            abort(404, message="Job not found.")
        return obj


@blp.route("/me/products")
class MyProducts(MethodView):
    @blp.arguments(PageArgsSchema, location="query")
    @blp.response(200, MyEditorialProductCollection)
    def get(self, args: dict) -> dict:
        """List the caller's own editorial products (any status)."""
        _require(Scope.READ_SELF)
        page = q.list_my_products(current_identity().id, args["limit"], args["offset"])
        return _collection("me/products", page)


@blp.route("/me/products/<int:product_id>")
class MyProduct(MethodView):
    @blp.response(200, MyEditorialProductSchema)
    def get(self, product_id: int):
        """Fetch one of the caller's own editorial products."""
        _require(Scope.READ_SELF)
        obj = q.get_my_product(current_identity().id, product_id)
        if obj is None:
            abort(404, message="Product not found.")
        return obj
