# Copyright (c) 2025, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only
"""End-to-end tests that drive the whole public API **through the Python SDK**.

Where ``test_api.py`` / ``test_me.py`` / ``test_write.py`` hit ``/api/v1``
directly with the Flask test client, these exercise the same surface via
``aipress24_client`` — proving the SDK is a faithful, complete client for the
current API (reads, owner-scoped ``/me`` reads, and the full write lifecycle).

No live server is needed: the SDK's ``_open`` transport is routed through the
Flask test client. Because the API is stateless (a bearer token per request),
one test client backs several SDK identities at once.
"""

from __future__ import annotations

import sys
import uuid
from pathlib import Path
from types import SimpleNamespace

import arrow
import pytest
from flask import Flask
from flask.testing import FlaskClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.enums import RoleEnum
from app.models.auth import Role, User
from app.models.lifecycle import PublicationStatus
from app.models.organisation import Organisation
from app.modules.api_v1.models import ApiToken
from app.modules.api_v1.security import ALL_SCOPES, Scope, generate_token
from app.modules.biz.models import MissionOffer
from app.modules.bw.bw_activation.models.business_wall import BusinessWall
from app.modules.bw.bw_activation.models.role import (
    BWRoleType,
    InvitationStatus,
    PermissionType,
    RoleAssignment,
    RolePermission,
)
from app.modules.wip.models import Article, AvisEnquete, Communique
from app.modules.wip.models.eventroom import Event

# The SDK is a standalone package under sdk/python (not installed); add it to
# the path exactly as the SDK unit tests do.
_SDK_PATH = Path(__file__).resolve().parents[4] / "sdk" / "python"
if str(_SDK_PATH) not in sys.path:
    sys.path.insert(0, str(_SDK_PATH))

from aipress24_client import COLLECTIONS, ApiError, Client, Page  # noqa: E402

DRAFT = PublicationStatus.DRAFT.value
PUBLIC = PublicationStatus.PUBLIC.value


# --- SDK transport over the Flask test client -----------------------------


class WsgiClient(Client):
    """An SDK ``Client`` whose HTTP goes through the Flask test client.

    ``base_url=""`` makes the SDK emit absolute ``/api/v1/…`` paths, which the
    Werkzeug test client accepts. Each request carries its own bearer token, so
    several ``WsgiClient`` instances (different identities) share one test
    client without any session cross-talk.
    """

    def __init__(self, flask_client: FlaskClient, token: str) -> None:
        super().__init__(token=token, base_url="")
        self._flask_client = flask_client

    def _open(self, url, headers, method="GET", data=None):
        response = self._flask_client.open(
            url, method=method, headers=headers, data=data
        )
        return response.status_code, response.data


@pytest.fixture
def make_sdk(client: FlaskClient):
    """Factory: build an SDK client bound to a token (over the test client)."""

    def _make(token: str) -> WsgiClient:
        return WsgiClient(client, token)

    return _make


# --- seed helpers ---------------------------------------------------------


def _email() -> str:
    return f"sdk-{uuid.uuid4().hex[:8]}@example.com"


def _role(db_session: Session, name: RoleEnum) -> Role:
    existing = db_session.scalar(select(Role).where(Role.name == name.name))
    if existing:
        return existing
    role = Role(name=name.name, description=name.value)
    db_session.add(role)
    db_session.flush()
    return role


def _mint(db_session: Session, user: User, scopes: list[str]) -> str:
    raw, digest, prefix = generate_token()
    db_session.add(
        ApiToken(
            name="t",
            token_hash=digest,
            token_prefix=prefix,
            user_id=user.id,
            scopes=list(scopes),
        )
    )
    db_session.commit()
    return raw


def _grant_pr_role(
    db_session: Session,
    user: User,
    org: Organisation,
    *,
    mission: PermissionType,
    mission_granted: bool,
) -> None:
    """Give ``user`` an accepted BWPRe role on ``org``'s BW (delegated PR mgr),
    optionally granting the given content-type mission."""
    bw_owner = User(email=_email(), active=True)
    db_session.add(bw_owner)
    db_session.flush()
    bw = BusinessWall(
        bw_type="micro",
        owner_id=bw_owner.id,  # not `user`, else owner-bypass grants all missions
        payer_id=bw_owner.id,
        organisation_id=org.id,
    )
    db_session.add(bw)
    db_session.flush()
    assignment = RoleAssignment(
        business_wall_id=bw.id,
        user_id=user.id,
        role_type=BWRoleType.BWPRE.value,
        invitation_status=InvitationStatus.ACCEPTED.value,
    )
    db_session.add(assignment)
    db_session.flush()
    if mission_granted:
        db_session.add(
            RolePermission(
                role_assignment_id=assignment.id,
                permission_type=mission.value,
                is_granted=True,
            )
        )
    db_session.commit()


@pytest.fixture
def authoring_seed(db_session: Session) -> SimpleNamespace:
    """Users, roles and owned draft content for the /me + write scenarios."""
    pr_role = _role(db_session, RoleEnum.PRESS_RELATIONS)
    jr_role = _role(db_session, RoleEnum.PRESS_MEDIA)

    org = Organisation(name=f"Agency {uuid.uuid4().hex[:6]}")
    other_org = Organisation(name=f"Other {uuid.uuid4().hex[:6]}")

    author = User(email=_email(), first_name="Pia", last_name="Ar", active=True)
    author.roles.append(pr_role)  # Com'room (press releases + events)
    author.organisation = org

    journalist = User(email=_email(), first_name="Jo", last_name="Urn", active=True)
    journalist.roles.append(jr_role)  # Newsroom (articles) + Eventroom
    journalist.organisation = org

    other = User(email=_email(), first_name="Al", last_name="Ien", active=True)
    other.roles.append(pr_role)
    other.organisation = other_org

    db_session.add_all([org, other_org, author, journalist, other])
    db_session.flush()

    # author's own draft content (for the /me reads)
    my_article = Article(
        owner=author,
        titre="My draft article",
        chapo="c",
        contenu="body",
        date_parution_prevue=arrow.now().datetime,
        media_id=org.id,
        commanditaire_id=author.id,
        status=DRAFT,
    )
    my_communique = Communique(
        owner=author,
        titre="My draft PR",
        chapo="c",
        contenu="body",
        publisher_id=org.id,
        status=DRAFT,
    )
    my_avis = AvisEnquete(
        owner=author,
        titre="My avis",
        commanditaire_id=author.id,
        media_id=org.id,
        date_debut_enquete=arrow.utcnow(),
        date_fin_enquete=arrow.utcnow(),
        date_bouclage=arrow.utcnow(),
        date_parution_prevue=arrow.utcnow(),
    )
    my_mission = MissionOffer(
        owner=author,
        title="My mission",
        status=DRAFT,
        contact_email="me@example.com",
    )

    # other user's content (for ownership isolation)
    other_article = Article(
        owner=other,
        titre="Not my article",
        date_parution_prevue=arrow.now().datetime,
        media_id=other_org.id,
        commanditaire_id=other.id,
        status=DRAFT,
    )
    other_communique = Communique(
        owner=other,
        titre="Not my PR",
        contenu="x",
        publisher_id=other_org.id,
        status=DRAFT,
    )
    other_event = Event(
        owner=other,
        titre="Not my event",
        contenu="x",
        publisher_id=other_org.id,
        status=DRAFT,
    )
    other_mission = MissionOffer(owner=other, title="Not my mission", status=DRAFT)

    db_session.add_all(
        [
            my_article,
            my_communique,
            my_avis,
            my_mission,
            other_article,
            other_communique,
            other_event,
            other_mission,
        ]
    )
    db_session.commit()

    return SimpleNamespace(
        org=org,
        other_org=other_org,
        author=author,
        journalist=journalist,
        other=other,
        my_article=my_article,
        my_communique=my_communique,
        my_mission=my_mission,
        other_article=other_article,
        other_communique=other_communique,
        other_event=other_event,
        other_mission=other_mission,
        author_all=_mint(db_session, author, ALL_SCOPES),
        author_readself=_mint(db_session, author, [Scope.READ_SELF.value]),
        author_content=_mint(db_session, author, [Scope.READ_CONTENT.value]),
        journalist_all=_mint(db_session, journalist, ALL_SCOPES),
    )


def _api_error(status: int, fn) -> ApiError:
    """Assert that calling ``fn`` raises ``ApiError`` with ``status``."""
    with pytest.raises(ApiError) as excinfo:
        fn()
    assert excinfo.value.status == status, excinfo.value.payload
    return excinfo.value


# ==========================================================================
# A. Discovery, auth and error mapping
# ==========================================================================


def test_root_discovery(make_sdk, seed) -> None:
    body = make_sdk(seed.token).root()
    assert body["api"] == "AIpress24 API"
    assert body["_links"]["articles"]["href"] == "/api/v1/articles"
    assert body["_links"]["docs"]["href"] == "/api/v1/docs"


def test_missing_token_raises_401(make_sdk, seed) -> None:
    _api_error(401, lambda: make_sdk("").articles())


def test_invalid_token_raises_401(make_sdk, seed) -> None:
    _api_error(401, lambda: make_sdk("a24_bogus").articles())


def test_unknown_collection_raises_404(make_sdk, seed) -> None:
    _api_error(404, lambda: make_sdk(seed.token).list("nope-not-a-collection"))


def test_write_to_readonly_collection_raises_405(make_sdk, seed) -> None:
    # POST to a GET-only public collection -> 405, surfaced as ApiError.
    _api_error(405, lambda: make_sdk(seed.token).create("articles", {"x": 1}))


def test_all_generated_collections_reachable(make_sdk, seed) -> None:
    # Every collection the SDK was generated to know about answers (200) with a
    # full-scope token — exercises the generated COLLECTIONS map end-to-end.
    api = make_sdk(seed.token)
    assert COLLECTIONS  # sanity: the generated list is non-empty
    for collection in COLLECTIONS:
        assert isinstance(api.list(collection), Page)


# ==========================================================================
# B. Public content reads
# ==========================================================================


def test_articles_list_only_published(make_sdk, seed) -> None:
    page = make_sdk(seed.token).articles()
    assert page.total == 3  # published only; draft + expired excluded
    assert {item["title"] for item in page} == {"Public 1", "Public 2", "Long body"}
    item = page.items[0]
    assert "owner_id" not in item  # PII redacted
    assert item["_links"]["self"]["href"].startswith("/api/v1/articles/")


def test_pagination_next_link_and_iter(make_sdk, seed) -> None:
    api = make_sdk(seed.token)
    first = api.articles(limit=1)
    assert len(first) == 1
    assert first.total == 3
    assert first.has_next
    second = first.next_page()
    assert second is not None and second.offset == 1
    # iter() walks every page via the `next` links.
    assert len(list(api.iter("articles", limit=1))) == 3


def test_article_detail_and_draft_404(make_sdk, seed) -> None:
    api = make_sdk(seed.token)
    assert api.article(seed.published_1.id)["id"] == seed.published_1.id
    _api_error(404, lambda: api.article(seed.draft.id))


def test_events_list_and_draft_404(make_sdk, seed) -> None:
    api = make_sdk(seed.token)
    page = api.events()
    assert page.total == 1
    assert page.items[0]["title"] == "Expo"
    _api_error(404, lambda: api.event(seed.draft_event.id))


def test_organisations_and_business_walls(make_sdk, seed) -> None:
    api = make_sdk(seed.token)
    assert api.organisations().total >= 1
    assert isinstance(api.business_walls(), Page)  # 200 even if empty


def test_members_redact_contact_details(make_sdk, seed) -> None:
    page = make_sdk(seed.token).members()
    assert page.total >= 1
    member = page.items[0]
    for leaked in ("email", "tel_mobile", "password", "fs_uniquifier", "is_clone"):
        assert leaked not in member


def test_scope_is_enforced(make_sdk, seed) -> None:
    api = make_sdk(seed.content_only_token)  # read:content only
    assert isinstance(api.articles(), Page)  # granted
    _api_error(403, api.members)  # not granted


def test_paywalled_body_gated_by_entitlement(
    make_sdk, seed, app: Flask, monkeypatch: pytest.MonkeyPatch
) -> None:
    full_body = seed.long_article.content
    author = make_sdk(seed.token)  # owns the article
    reader = make_sdk(seed.reader_token)  # not entitled

    monkeypatch.setitem(app.config, "STRIPE_LIVE_ENABLED", True)
    reader_body = reader.article(seed.long_article.id)["content"]
    assert reader_body != full_body
    assert len(reader_body) < len(full_body)
    assert author.article(seed.long_article.id)["content"] == full_body

    monkeypatch.setitem(app.config, "STRIPE_LIVE_ENABLED", False)
    assert reader.article(seed.long_article.id)["content"] == full_body


# ==========================================================================
# C. Owner-scoped reads (/me)
# ==========================================================================


def test_me_profile(make_sdk, authoring_seed) -> None:
    body = make_sdk(authoring_seed.author_all).me()
    assert body["id"] == authoring_seed.author.id
    assert body["email"] == authoring_seed.author.email  # own detail, not redacted
    assert body["_links"]["self"]["href"] == "/api/v1/me"
    for leak in ("password", "fs_uniquifier", "is_clone"):
        assert leak not in body


def test_me_requires_read_self_scope(make_sdk, authoring_seed) -> None:
    _api_error(403, make_sdk(authoring_seed.author_content).me)


def test_me_articles_lists_only_own(make_sdk, authoring_seed) -> None:
    titles = {
        i["titre"] for i in make_sdk(authoring_seed.author_all).list("me/articles")
    }
    assert "My draft article" in titles
    assert "Not my article" not in titles


def test_me_detail_isolation(make_sdk, authoring_seed) -> None:
    api = make_sdk(authoring_seed.author_all)
    assert api.get_one("me/articles", authoring_seed.my_article.id)["titre"]
    _api_error(404, lambda: api.get_one("me/articles", authoring_seed.other_article.id))


def test_me_press_releases_and_enquiry_notices(make_sdk, authoring_seed) -> None:
    api = make_sdk(authoring_seed.author_all)
    assert api.list("me/press-releases").total == 1
    assert api.list("me/enquiry-notices").total == 1


def test_me_marketplace_only_own(make_sdk, authoring_seed) -> None:
    api = make_sdk(authoring_seed.author_all)
    missions = api.list("me/missions").items
    titles = {m["title"] for m in missions}
    assert "My mission" in titles
    assert "Not my mission" not in titles
    mine = next(m for m in missions if m["title"] == "My mission")
    assert mine["contact_email"] == "me@example.com"  # own offer, own email
    _api_error(404, lambda: api.get_one("me/missions", authoring_seed.other_mission.id))


# ==========================================================================
# D. Writes — press releases
# ==========================================================================


def _create_pr(api: WsgiClient, **body) -> dict:
    body.setdefault("titre", "Hello world")
    return api.create("me/press-releases", body)


def test_pr_create_and_list_own(make_sdk, authoring_seed) -> None:
    api = make_sdk(authoring_seed.author_all)
    created = _create_pr(api, contenu="<p>Body</p>")
    assert created["status"] == DRAFT
    assert created["publisher_id"] == authoring_seed.org.id  # defaulted to own org
    # own drafts (the fixture's + this one) show up
    assert api.list("me/press-releases").total == 2


def test_pr_create_requires_write_scope(make_sdk, authoring_seed) -> None:
    api = make_sdk(authoring_seed.author_readself)  # read:self, no write:content
    _api_error(403, lambda: _create_pr(api))


def test_pr_create_denied_for_journalist(make_sdk, authoring_seed) -> None:
    _api_error(403, lambda: _create_pr(make_sdk(authoring_seed.journalist_all)))


def test_pr_sanitizes_body_but_not_title(make_sdk, authoring_seed) -> None:
    created = _create_pr(
        make_sdk(authoring_seed.author_all),
        titre="R&D funding & AT&T",
        contenu="<script>evil()</script><p>Clean</p>",
    )
    assert "<script" not in created["contenu"]
    assert "Clean" in created["contenu"]
    assert created["titre"] == "R&D funding & AT&T"  # verbatim, no entity corruption


def test_pr_publish_creates_public_mirror(make_sdk, authoring_seed) -> None:
    api = make_sdk(authoring_seed.author_all)
    created = _create_pr(api, contenu="<p>Body</p>")
    published = api.publish("me/press-releases", created["id"])
    assert published["status"] == PUBLIC
    titles = {pr["title"] for pr in api.press_releases()}
    assert "Hello world" in titles


def test_pr_publish_requires_content(make_sdk, authoring_seed) -> None:
    api = make_sdk(authoring_seed.author_all)
    created = _create_pr(api)  # no body
    _api_error(422, lambda: api.publish("me/press-releases", created["id"]))


def test_pr_publish_for_unauthorized_org_forbidden(make_sdk, authoring_seed) -> None:
    api = make_sdk(authoring_seed.author_all)
    _api_error(
        403,
        lambda: _create_pr(api, publisher_id=authoring_seed.other_org.id),
    )


def test_pr_update_is_partial(make_sdk, authoring_seed) -> None:
    api = make_sdk(authoring_seed.author_all)
    created = _create_pr(api, contenu="<p>Original</p>")
    updated = api.update("me/press-releases", created["id"], {"titre": "New title"})
    assert updated["titre"] == "New title"
    assert "Original" in updated["contenu"]  # untouched field survives


def test_pr_unpublish_removes_mirror(make_sdk, authoring_seed) -> None:
    api = make_sdk(authoring_seed.author_all)
    created = _create_pr(api, contenu="<p>Body</p>")
    api.publish("me/press-releases", created["id"])
    back = api.unpublish("me/press-releases", created["id"])
    assert back["status"] == DRAFT
    assert "Hello world" not in {pr["title"] for pr in api.press_releases()}


def test_pr_delete_soft_deletes(make_sdk, authoring_seed) -> None:
    api = make_sdk(authoring_seed.author_all)
    created = _create_pr(api, contenu="<p>Body</p>")
    api.delete("me/press-releases", created["id"])
    _api_error(404, lambda: api.get_one("me/press-releases", created["id"]))


def test_pr_cannot_touch_another_users(make_sdk, authoring_seed) -> None:
    api = make_sdk(authoring_seed.author_all)
    pr_id = authoring_seed.other_communique.id
    _api_error(404, lambda: api.update("me/press-releases", pr_id, {"titre": "x"}))
    _api_error(404, lambda: api.publish("me/press-releases", pr_id))
    _api_error(404, lambda: api.delete("me/press-releases", pr_id))


def test_pr_delete_requires_room_access(make_sdk, authoring_seed, db_session) -> None:
    # The journalist owns this press release but has no Com'room access, so —
    # as in the portal — even deleting their own row is refused (403, not 404).
    row = Communique(
        owner=authoring_seed.journalist,
        titre="Stale role",
        contenu="<p>x</p>",
        publisher_id=authoring_seed.org.id,
        status=PublicationStatus.DRAFT,
    )
    db_session.add(row)
    db_session.commit()
    api = make_sdk(authoring_seed.journalist_all)
    _api_error(403, lambda: api.delete("me/press-releases", row.id))


# ==========================================================================
# E. Writes — articles (journalists only, own-org)
# ==========================================================================


def test_article_create_draft(make_sdk, authoring_seed) -> None:
    created = make_sdk(authoring_seed.journalist_all).create(
        "me/articles", {"titre": "My article", "contenu": "<p>Body</p>"}
    )
    assert created["status"] == DRAFT
    assert created["media_id"] == authoring_seed.org.id  # own-org, server-set
    assert created["commanditaire_id"] == authoring_seed.journalist.id


def test_article_create_denied_for_non_journalist(make_sdk, authoring_seed) -> None:
    _api_error(
        403,
        lambda: make_sdk(authoring_seed.author_all).create(
            "me/articles", {"titre": "x"}
        ),
    )


def test_article_publish_creates_public_mirror(make_sdk, authoring_seed) -> None:
    api = make_sdk(authoring_seed.journalist_all)
    created = api.create("me/articles", {"titre": "SDK scoop", "contenu": "<p>b</p>"})
    assert api.publish("me/articles", created["id"])["status"] == PUBLIC
    assert "SDK scoop" in {a["title"] for a in api.articles()}


def test_article_publish_requires_content(make_sdk, authoring_seed) -> None:
    api = make_sdk(authoring_seed.journalist_all)
    created = api.create("me/articles", {"titre": "No body"})
    _api_error(422, lambda: api.publish("me/articles", created["id"]))


def test_article_ownership_enforced(make_sdk, authoring_seed) -> None:
    api = make_sdk(authoring_seed.journalist_all)
    art_id = authoring_seed.other_article.id
    _api_error(404, lambda: api.publish("me/articles", art_id))
    _api_error(404, lambda: api.delete("me/articles", art_id))


# ==========================================================================
# F. Writes — events (on-behalf allowed, date rules)
# ==========================================================================


def test_event_create_and_list(make_sdk, authoring_seed) -> None:
    api = make_sdk(authoring_seed.author_all)
    created = api.create("me/events", {"titre": "My event", "contenu": "<p>b</p>"})
    assert created["status"] == DRAFT
    assert api.list("me/events").total == 1


def test_event_publish_requires_dates(make_sdk, authoring_seed) -> None:
    api = make_sdk(authoring_seed.author_all)
    created = api.create("me/events", {"titre": "Dateless", "contenu": "<p>b</p>"})
    _api_error(422, lambda: api.publish("me/events", created["id"]))


def test_event_publish_with_dates_creates_mirror(make_sdk, authoring_seed) -> None:
    api = make_sdk(authoring_seed.author_all)
    created = api.create(
        "me/events",
        {
            "titre": "SDK expo",
            "contenu": "<p>b</p>",
            "start_time": arrow.now().shift(days=1).isoformat(),
            "end_time": arrow.now().shift(days=1, hours=2).isoformat(),
        },
    )
    assert api.publish("me/events", created["id"])["status"] == PUBLIC
    assert "SDK expo" in {e["title"] for e in api.events()}


def test_event_publish_rejects_end_before_start(make_sdk, authoring_seed) -> None:
    api = make_sdk(authoring_seed.author_all)
    created = api.create(
        "me/events",
        {
            "titre": "Backwards",
            "contenu": "<p>b</p>",
            "start_time": arrow.now().shift(days=2).isoformat(),
            "end_time": arrow.now().shift(days=1).isoformat(),
        },
    )
    _api_error(422, lambda: api.publish("me/events", created["id"]))


def test_event_ownership_enforced(make_sdk, authoring_seed) -> None:
    api = make_sdk(authoring_seed.author_all)
    ev_id = authoring_seed.other_event.id
    _api_error(404, lambda: api.get_one("me/events", ev_id))
    _api_error(404, lambda: api.delete("me/events", ev_id))


def test_event_create_for_unauthorized_org_forbidden(make_sdk, authoring_seed) -> None:
    # No relationship to other_org -> attribution refused at create (fail closed).
    api = make_sdk(authoring_seed.author_all)
    _api_error(
        403,
        lambda: api.create(
            "me/events",
            {"titre": "x", "publisher_id": authoring_seed.other_org.id},
        ),
    )


# ==========================================================================
# G. On-behalf mission gate (delegated PR manager)
# ==========================================================================


def test_onbehalf_denied_without_mission(make_sdk, authoring_seed, db_session) -> None:
    _grant_pr_role(
        db_session,
        authoring_seed.author,
        authoring_seed.other_org,
        mission=PermissionType.PRESS_RELEASE,
        mission_granted=False,
    )
    api = make_sdk(authoring_seed.author_all)
    _api_error(
        403,
        lambda: api.create(
            "me/press-releases",
            {"titre": "x", "publisher_id": authoring_seed.other_org.id},
        ),
    )


def test_onbehalf_allowed_with_mission(make_sdk, authoring_seed, db_session) -> None:
    _grant_pr_role(
        db_session,
        authoring_seed.author,
        authoring_seed.other_org,
        mission=PermissionType.PRESS_RELEASE,
        mission_granted=True,
    )
    api = make_sdk(authoring_seed.author_all)
    created = api.create(
        "me/press-releases",
        {
            "titre": "For our client",
            "contenu": "<p>b</p>",
            "publisher_id": authoring_seed.other_org.id,
        },
    )
    assert created["publisher_id"] == authoring_seed.other_org.id
    assert api.publish("me/press-releases", created["id"])["status"] == PUBLIC
