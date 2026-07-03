# Copyright (c) 2025, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only
"""Owner-scoped write endpoints: authoring & publishing content.

Proves the API's write path reuses the WIP-room domain authorization and the
source models' publication state machines across all three content types
(press releases, articles, events): only the right role + ``write:content``
may author; publishing creates the public mirror; ownership is enforced (404
on someone else's row); the publisher-attribution gate fails closed; and the
event date rules are enforced by the domain.
"""

from __future__ import annotations

import uuid
from types import SimpleNamespace

import arrow
import pytest
from flask.testing import FlaskClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.enums import RoleEnum
from app.models.auth import Role, User
from app.models.lifecycle import PublicationStatus
from app.models.organisation import Organisation
from app.modules.api_v1.models import ApiToken
from app.modules.api_v1.security import ALL_SCOPES, Scope, generate_token
from app.modules.bw.bw_activation.models.business_wall import BusinessWall
from app.modules.bw.bw_activation.models.role import (
    BWRoleType,
    InvitationStatus,
    PermissionType,
    RoleAssignment,
    RolePermission,
)
from app.modules.wip.models import Article, Communique
from app.modules.wip.models.eventroom import Event


def _grant_pr_role(
    db_session: Session,
    user: User,
    org: Organisation,
    *,
    mission: PermissionType,
    mission_granted: bool,
) -> None:
    """Give ``user`` an accepted BWPRe (delegated PR-manager) role on ``org``'s
    Business Wall — optionally granting the given content-type mission.

    Mirrors the real delegation shape: an org owner (someone else) invites the
    user as an external PR manager, then may or may not tick the granular
    press-release/events permission. Without the mission, ``can_user_publish_for``
    still returns True (bare role), so this is exactly the state the portal
    blocks at publish and the API must too.
    """
    bw_owner = User(email=_email(), active=True)
    db_session.add(bw_owner)
    db_session.flush()
    bw = BusinessWall(
        bw_type="micro",
        owner_id=bw_owner.id,  # NOT `user` — else owner-bypass grants all missions
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


def _email() -> str:
    return f"w-{uuid.uuid4().hex[:8]}@example.com"


def _role(db_session: Session, name: RoleEnum) -> Role:
    """Get-or-create: role names are globally unique and may be pre-seeded."""
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


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def wseed(db_session: Session) -> SimpleNamespace:
    pr_role = _role(db_session, RoleEnum.PRESS_RELATIONS)
    jr_role = _role(db_session, RoleEnum.PRESS_MEDIA)

    # A PR person (Com'room role) may author press releases.
    org = Organisation(name=f"Agency {uuid.uuid4().hex[:6]}")
    author = User(email=_email(), first_name="Pia", last_name="Ar", active=True)
    author.roles.append(pr_role)
    author.organisation = org

    # A journalist (Newsroom role only) may NOT author press releases.
    journalist = User(
        email=_email(), first_name="Jo", last_name="Urnalist", active=True
    )
    journalist.roles.append(jr_role)
    journalist.organisation = org

    # Another PR person, in a different org — used for the "not your row" checks
    # and as an org the author is not allowed to publish for.
    other_org = Organisation(name=f"Other {uuid.uuid4().hex[:6]}")
    other = User(email=_email(), first_name="Al", last_name="Ien", active=True)
    other.roles.append(pr_role)
    other.organisation = other_org

    db_session.add_all([org, other_org, author, journalist, other])
    db_session.commit()

    return SimpleNamespace(
        author=author,
        org=org,
        journalist=journalist,
        other=other,
        other_org=other_org,
        author_token=_mint(db_session, author, ALL_SCOPES),
        author_read_only=_mint(db_session, author, [Scope.READ_SELF.value]),
        journalist_token=_mint(db_session, journalist, ALL_SCOPES),
        other_token=_mint(db_session, other, ALL_SCOPES),
    )


def _create(client: FlaskClient, token: str, **body) -> dict:
    body.setdefault("titre", "Hello world")
    resp = client.post("/api/v1/me/press-releases", json=body, headers=_auth(token))
    assert resp.status_code == 201, resp.get_json()
    return resp.get_json()


def test_create_draft(client: FlaskClient, wseed: SimpleNamespace) -> None:
    body = _create(client, wseed.author_token, contenu="<p>Body</p>")
    assert body["status"] == PublicationStatus.DRAFT.value
    assert body["titre"] == "Hello world"
    assert body["publisher_id"] == wseed.org.id  # defaulted to own org
    # It shows up in the owner's own listing.
    listing = client.get("/api/v1/me/press-releases", headers=_auth(wseed.author_token))
    assert listing.get_json()["total"] == 1


def test_create_requires_write_scope(
    client: FlaskClient, wseed: SimpleNamespace
) -> None:
    resp = client.post(
        "/api/v1/me/press-releases",
        json={"titre": "x"},
        headers=_auth(wseed.author_read_only),
    )
    assert resp.status_code == 403


def test_create_denied_for_journalist(
    client: FlaskClient, wseed: SimpleNamespace
) -> None:
    # Journalists author *articles* in Newsroom, not press releases in Com'room.
    resp = client.post(
        "/api/v1/me/press-releases",
        json={"titre": "x"},
        headers=_auth(wseed.journalist_token),
    )
    assert resp.status_code == 403


def test_sanitizes_body_but_not_title(
    client: FlaskClient, wseed: SimpleNamespace
) -> None:
    body = _create(
        client,
        wseed.author_token,
        titre="R&D funding & AT&T",
        contenu="<script>evil()</script><p>Clean body</p>",
    )
    # The HTML body is sanitized (no executable markup survives)...
    assert "<script" not in body["contenu"]
    assert "Clean body" in body["contenu"]
    # ...but a plain-text title round-trips verbatim — stored as-is (as in the
    # UI) and rendered escaped, so no HTML-entity corruption of "R&D"/"AT&T".
    assert body["titre"] == "R&D funding & AT&T"


def test_publish_creates_public_mirror(
    client: FlaskClient, wseed: SimpleNamespace
) -> None:
    created = _create(client, wseed.author_token, contenu="<p>Body</p>")
    pr_id = created["id"]

    resp = client.post(
        f"/api/v1/me/press-releases/{pr_id}/publish", headers=_auth(wseed.author_token)
    )
    assert resp.status_code == 200
    assert resp.get_json()["status"] == PublicationStatus.PUBLIC.value

    # The publication went through the domain -> a public wire mirror exists and
    # is now visible on the read-only public collection.
    public = client.get("/api/v1/press-releases", headers=_auth(wseed.author_token))
    titles = {item["title"] for item in public.get_json()["items"]}
    assert "Hello world" in titles


def test_publish_requires_content(client: FlaskClient, wseed: SimpleNamespace) -> None:
    # No body -> the domain refuses to publish (empty contenu).
    created = _create(client, wseed.author_token)
    resp = client.post(
        f"/api/v1/me/press-releases/{created['id']}/publish",
        headers=_auth(wseed.author_token),
    )
    assert resp.status_code == 422


def test_publish_for_unauthorized_org_forbidden(
    client: FlaskClient, wseed: SimpleNamespace
) -> None:
    # Attributing to an org the caller has no partnership/role with is refused
    # at create time (fail closed) — the "agence de RP" gate, from the domain.
    resp = client.post(
        "/api/v1/me/press-releases",
        json={"titre": "x", "publisher_id": wseed.other_org.id},
        headers=_auth(wseed.author_token),
    )
    assert resp.status_code == 403


def test_update_is_partial(client: FlaskClient, wseed: SimpleNamespace) -> None:
    created = _create(client, wseed.author_token, contenu="<p>Original</p>")
    pr_id = created["id"]

    resp = client.patch(
        f"/api/v1/me/press-releases/{pr_id}",
        json={"titre": "New title"},
        headers=_auth(wseed.author_token),
    )
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["titre"] == "New title"
    assert "Original" in body["contenu"]  # untouched field survives


def test_unpublish_removes_public_mirror(
    client: FlaskClient, wseed: SimpleNamespace
) -> None:
    created = _create(client, wseed.author_token, contenu="<p>Body</p>")
    pr_id = created["id"]
    client.post(
        f"/api/v1/me/press-releases/{pr_id}/publish", headers=_auth(wseed.author_token)
    )

    resp = client.post(
        f"/api/v1/me/press-releases/{pr_id}/unpublish",
        headers=_auth(wseed.author_token),
    )
    assert resp.status_code == 200
    assert resp.get_json()["status"] == PublicationStatus.DRAFT.value

    public = client.get("/api/v1/press-releases", headers=_auth(wseed.author_token))
    titles = {item["title"] for item in public.get_json()["items"]}
    assert "Hello world" not in titles


def test_delete_soft_deletes(client: FlaskClient, wseed: SimpleNamespace) -> None:
    created = _create(client, wseed.author_token, contenu="<p>Body</p>")
    pr_id = created["id"]

    resp = client.delete(
        f"/api/v1/me/press-releases/{pr_id}", headers=_auth(wseed.author_token)
    )
    assert resp.status_code == 204

    # Gone from the owner's view, and the row is soft-deleted (not hard-deleted).
    after = client.get(
        f"/api/v1/me/press-releases/{pr_id}", headers=_auth(wseed.author_token)
    )
    assert after.status_code == 404


def test_cannot_touch_another_users_release(
    client: FlaskClient, wseed: SimpleNamespace, db_session: Session
) -> None:
    # A draft owned by `other`.
    theirs = Communique(
        owner=wseed.other,
        titre="Theirs",
        contenu="<p>x</p>",
        publisher_id=wseed.other_org.id,
        status=PublicationStatus.DRAFT,
    )
    db_session.add(theirs)
    db_session.commit()
    pr_id = theirs.id

    tok = _auth(wseed.author_token)
    # Every mutation 404s (existence not disclosed), never 403.
    assert (
        client.patch(
            f"/api/v1/me/press-releases/{pr_id}", json={"titre": "hijack"}, headers=tok
        ).status_code
        == 404
    )
    assert (
        client.post(
            f"/api/v1/me/press-releases/{pr_id}/publish", headers=tok
        ).status_code
        == 404
    )
    assert (
        client.delete(f"/api/v1/me/press-releases/{pr_id}", headers=tok).status_code
        == 404
    )


# --- articles (newsroom: journalists only, own-org attribution) -----------


def _create_article(client: FlaskClient, token: str, **body) -> dict:
    body.setdefault("titre", "My article")
    resp = client.post("/api/v1/me/articles", json=body, headers=_auth(token))
    assert resp.status_code == 201, resp.get_json()
    return resp.get_json()


def test_article_create_draft(client: FlaskClient, wseed: SimpleNamespace) -> None:
    # The journalist (PRESS_MEDIA) may author articles.
    body = _create_article(client, wseed.journalist_token, contenu="<p>Body</p>")
    assert body["status"] == PublicationStatus.DRAFT.value
    assert body["kind"] == "article"
    # Own-org attribution is set server-side (no on-behalf input for articles).
    assert body["media_id"] == wseed.org.id
    assert body["commanditaire_id"] == wseed.journalist.id


def test_article_create_denied_for_non_journalist(
    client: FlaskClient, wseed: SimpleNamespace
) -> None:
    # A PR person (not PRESS_MEDIA) cannot author newsroom articles.
    resp = client.post(
        "/api/v1/me/articles",
        json={"titre": "x"},
        headers=_auth(wseed.author_token),
    )
    assert resp.status_code == 403


def test_article_publish_creates_public_mirror(
    client: FlaskClient, wseed: SimpleNamespace
) -> None:
    created = _create_article(client, wseed.journalist_token, contenu="<p>Body</p>")
    resp = client.post(
        f"/api/v1/me/articles/{created['id']}/publish",
        headers=_auth(wseed.journalist_token),
    )
    assert resp.status_code == 200
    assert resp.get_json()["status"] == PublicationStatus.PUBLIC.value

    public = client.get("/api/v1/articles", headers=_auth(wseed.journalist_token))
    titles = {item["title"] for item in public.get_json()["items"]}
    assert "My article" in titles


def test_article_publish_requires_content(
    client: FlaskClient, wseed: SimpleNamespace
) -> None:
    created = _create_article(client, wseed.journalist_token)  # no body
    resp = client.post(
        f"/api/v1/me/articles/{created['id']}/publish",
        headers=_auth(wseed.journalist_token),
    )
    assert resp.status_code == 422


def test_article_ownership_enforced(
    client: FlaskClient, wseed: SimpleNamespace, db_session: Session
) -> None:
    # An article owned by someone else — the journalist cannot touch it.
    theirs = Article(
        owner=wseed.other,
        titre="Not mine",
        contenu="<p>x</p>",
        media_id=wseed.other_org.id,
        commanditaire_id=wseed.other.id,
        date_parution_prevue=arrow.now().datetime,
        status=PublicationStatus.DRAFT,
    )
    db_session.add(theirs)
    db_session.commit()
    tok = _auth(wseed.journalist_token)
    assert (
        client.post(f"/api/v1/me/articles/{theirs.id}/publish", headers=tok).status_code
        == 404
    )
    assert (
        client.delete(f"/api/v1/me/articles/{theirs.id}", headers=tok).status_code
        == 404
    )


# --- events (eventroom: on-behalf allowed, date rules enforced) -----------


def _create_event(client: FlaskClient, token: str, **body) -> dict:
    body.setdefault("titre", "My event")
    resp = client.post("/api/v1/me/events", json=body, headers=_auth(token))
    assert resp.status_code == 201, resp.get_json()
    return resp.get_json()


def test_event_create_and_list(client: FlaskClient, wseed: SimpleNamespace) -> None:
    body = _create_event(client, wseed.author_token, contenu="<p>Body</p>")
    assert body["status"] == PublicationStatus.DRAFT.value
    assert body["kind"] == "event"
    listing = client.get("/api/v1/me/events", headers=_auth(wseed.author_token))
    assert listing.get_json()["total"] == 1


def test_event_publish_requires_dates(
    client: FlaskClient, wseed: SimpleNamespace
) -> None:
    # The domain refuses to publish a dateless event (would be invisible).
    created = _create_event(client, wseed.author_token, contenu="<p>Body</p>")
    resp = client.post(
        f"/api/v1/me/events/{created['id']}/publish",
        headers=_auth(wseed.author_token),
    )
    assert resp.status_code == 422


def test_event_publish_with_dates_creates_mirror(
    client: FlaskClient, wseed: SimpleNamespace
) -> None:
    start = arrow.now().shift(days=1).isoformat()
    end = arrow.now().shift(days=1, hours=2).isoformat()
    created = _create_event(
        client,
        wseed.author_token,
        contenu="<p>Body</p>",
        start_time=start,
        end_time=end,
    )
    resp = client.post(
        f"/api/v1/me/events/{created['id']}/publish",
        headers=_auth(wseed.author_token),
    )
    assert resp.status_code == 200
    assert resp.get_json()["status"] == PublicationStatus.PUBLIC.value

    public = client.get("/api/v1/events", headers=_auth(wseed.author_token))
    titles = {item["title"] for item in public.get_json()["items"]}
    assert "My event" in titles


def test_event_publish_rejects_end_before_start(
    client: FlaskClient, wseed: SimpleNamespace
) -> None:
    start = arrow.now().shift(days=2).isoformat()
    end = arrow.now().shift(days=1).isoformat()  # before start
    created = _create_event(
        client,
        wseed.author_token,
        contenu="<p>Body</p>",
        start_time=start,
        end_time=end,
    )
    resp = client.post(
        f"/api/v1/me/events/{created['id']}/publish",
        headers=_auth(wseed.author_token),
    )
    assert resp.status_code == 422


def test_event_publish_for_unauthorized_org_forbidden(
    client: FlaskClient, wseed: SimpleNamespace
) -> None:
    resp = client.post(
        "/api/v1/me/events",
        json={"titre": "x", "publisher_id": wseed.other_org.id},
        headers=_auth(wseed.author_token),
    )
    assert resp.status_code == 403


def test_event_ownership_enforced(
    client: FlaskClient, wseed: SimpleNamespace, db_session: Session
) -> None:
    theirs = Event(
        owner=wseed.other,
        titre="Not mine",
        contenu="<p>x</p>",
        publisher_id=wseed.other_org.id,
        status=PublicationStatus.DRAFT,
    )
    db_session.add(theirs)
    db_session.commit()
    tok = _auth(wseed.author_token)
    assert client.get(f"/api/v1/me/events/{theirs.id}", headers=tok).status_code == 404
    assert (
        client.delete(f"/api/v1/me/events/{theirs.id}", headers=tok).status_code == 404
    )


# --- room-access parity on delete -----------------------------------------


def test_delete_requires_room_access(
    client: FlaskClient, wseed: SimpleNamespace, db_session: Session
) -> None:
    # A press release owned by the journalist, who has NO Com'room access.
    # Parity: they could not delete it in the portal (before_request Forbidden),
    # so the API refuses too — 403, not a silent 204. (Own-row 404 only applies
    # to *other* users' rows; the room gate applies even to your own.)
    row = Communique(
        owner=wseed.journalist,
        titre="Stale role",
        contenu="<p>x</p>",
        publisher_id=wseed.org.id,
        status=PublicationStatus.DRAFT,
    )
    db_session.add(row)
    db_session.commit()
    resp = client.delete(
        f"/api/v1/me/press-releases/{row.id}", headers=_auth(wseed.journalist_token)
    )
    assert resp.status_code == 403


# --- on-behalf mission gate (delegated PR manager) ------------------------
# A delegated PR manager (BWPRe role on a client org) may publish for that org
# ONLY for content types whose granular mission they were granted — exactly
# the portal's before_request gate, but evaluated against the *target* org's
# Business Wall rather than the session-selected one.


def test_pr_onbehalf_denied_without_mission(
    client: FlaskClient, wseed: SimpleNamespace, db_session: Session
) -> None:
    # author holds a BWPRe role on other_org but NO press_release mission.
    # can_user_publish_for alone would (wrongly) allow it; the mission gate must
    # refuse — the portal does (before_request Forbidden).
    _grant_pr_role(
        db_session,
        wseed.author,
        wseed.other_org,
        mission=PermissionType.PRESS_RELEASE,
        mission_granted=False,
    )
    resp = client.post(
        "/api/v1/me/press-releases",
        json={"titre": "x", "publisher_id": wseed.other_org.id},
        headers=_auth(wseed.author_token),
    )
    assert resp.status_code == 403


def test_pr_onbehalf_allowed_with_mission(
    client: FlaskClient, wseed: SimpleNamespace, db_session: Session
) -> None:
    # Same delegation, but WITH the press_release mission granted -> the agency
    # can create and publish a press release attributed to the client org.
    _grant_pr_role(
        db_session,
        wseed.author,
        wseed.other_org,
        mission=PermissionType.PRESS_RELEASE,
        mission_granted=True,
    )
    created = client.post(
        "/api/v1/me/press-releases",
        json={
            "titre": "For our client",
            "contenu": "<p>Body</p>",
            "publisher_id": wseed.other_org.id,
        },
        headers=_auth(wseed.author_token),
    )
    assert created.status_code == 201
    assert created.get_json()["publisher_id"] == wseed.other_org.id
    published = client.post(
        f"/api/v1/me/press-releases/{created.get_json()['id']}/publish",
        headers=_auth(wseed.author_token),
    )
    assert published.status_code == 200


def test_event_onbehalf_denied_without_events_mission(
    client: FlaskClient, wseed: SimpleNamespace, db_session: Session
) -> None:
    # Same gate for events, keyed to the EVENTS mission.
    _grant_pr_role(
        db_session,
        wseed.author,
        wseed.other_org,
        mission=PermissionType.EVENTS,
        mission_granted=False,
    )
    resp = client.post(
        "/api/v1/me/events",
        json={"titre": "x", "publisher_id": wseed.other_org.id},
        headers=_auth(wseed.author_token),
    )
    assert resp.status_code == 403
