# Copyright (c) 2025, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only
"""Owner-scoped /api/v1/me endpoints: a token reaches only its user's own data."""

from __future__ import annotations

import uuid
from types import SimpleNamespace

import arrow
import pytest
from flask.testing import FlaskClient
from sqlalchemy.orm import Session

from app.enums import RoleEnum
from app.models.auth import Role, User
from app.models.lifecycle import PublicationStatus
from app.models.organisation import Organisation
from app.modules.api_v1.models import ApiToken
from app.modules.api_v1.security import ALL_SCOPES, Scope, generate_token
from app.modules.biz.models import MissionOffer
from app.modules.wip.models import Article, AvisEnquete, Communique


def _email() -> str:
    return f"me-{uuid.uuid4().hex[:8]}@example.com"


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
def me_seed(db_session: Session) -> SimpleNamespace:
    role = Role(name=RoleEnum.PRESS_MEDIA.name, description=RoleEnum.PRESS_MEDIA.value)
    org = Organisation(name=f"Org {uuid.uuid4().hex[:6]}")
    owner = User(email=_email(), first_name="Owen", last_name="Er", active=True)
    owner.roles.append(role)
    owner.organisation = org
    other = User(email=_email(), active=True)
    db_session.add_all([role, org, owner, other])
    db_session.flush()

    my_article = Article(
        owner=owner,
        titre="My draft",
        chapo="c",
        contenu="body",
        date_parution_prevue=arrow.now().datetime,
        media_id=org.id,
        commanditaire_id=owner.id,
        status=PublicationStatus.DRAFT,
    )
    my_communique = Communique(
        owner=owner,
        titre="My PR",
        chapo="c",
        contenu="body",
        publisher_id=org.id,
        status=PublicationStatus.DRAFT,
    )
    my_avis = AvisEnquete(
        owner=owner,
        titre="My avis",
        commanditaire_id=owner.id,
        media_id=org.id,
        date_debut_enquete=arrow.utcnow(),
        date_fin_enquete=arrow.utcnow(),
        date_bouclage=arrow.utcnow(),
        date_parution_prevue=arrow.utcnow(),
    )
    other_article = Article(
        owner=other,
        titre="Not mine",
        date_parution_prevue=arrow.now().datetime,
        media_id=org.id,
        commanditaire_id=other.id,
    )
    my_mission = MissionOffer(
        owner=owner,
        title="My mission",
        status=PublicationStatus.DRAFT,
        contact_email="me@example.com",
    )
    other_mission = MissionOffer(
        owner=other, title="Not my mission", status=PublicationStatus.DRAFT
    )
    db_session.add_all(
        [my_article, my_communique, my_avis, other_article, my_mission, other_mission]
    )
    db_session.commit()

    return SimpleNamespace(
        owner=owner,
        my_article=my_article,
        my_communique=my_communique,
        my_avis=my_avis,
        other_article=other_article,
        my_mission=my_mission,
        other_mission=other_mission,
        token=_mint(db_session, owner, ALL_SCOPES),
        content_only=_mint(db_session, owner, [Scope.READ_CONTENT.value]),
    )


def test_me_returns_own_profile(client: FlaskClient, me_seed: SimpleNamespace) -> None:
    response = client.get("/api/v1/me", headers=_auth(me_seed.token))
    assert response.status_code == 200
    body = response.get_json()
    assert body["id"] == me_seed.owner.id
    assert body["email"] == me_seed.owner.email  # own contact detail, not redacted
    assert body["_links"]["self"]["href"] == "/api/v1/me"
    for leak in ("password", "fs_uniquifier", "is_clone", "email_safe_copy"):
        assert leak not in body


def test_me_requires_read_self_scope(
    client: FlaskClient, me_seed: SimpleNamespace
) -> None:
    response = client.get("/api/v1/me", headers=_auth(me_seed.content_only))
    assert response.status_code == 403


def test_me_articles_lists_only_own(
    client: FlaskClient, me_seed: SimpleNamespace
) -> None:
    response = client.get("/api/v1/me/articles", headers=_auth(me_seed.token))
    assert response.status_code == 200
    titles = {item["titre"] for item in response.get_json()["items"]}
    assert "My draft" in titles  # own draft is visible
    assert "Not mine" not in titles  # someone else's is not


def test_me_article_detail_404_for_someone_elses(
    client: FlaskClient, me_seed: SimpleNamespace
) -> None:
    mine = client.get(
        f"/api/v1/me/articles/{me_seed.my_article.id}", headers=_auth(me_seed.token)
    )
    assert mine.status_code == 200

    theirs = client.get(
        f"/api/v1/me/articles/{me_seed.other_article.id}", headers=_auth(me_seed.token)
    )
    assert theirs.status_code == 404  # 404, not 403 — existence not disclosed


def test_me_press_releases_and_enquiry_notices(
    client: FlaskClient, me_seed: SimpleNamespace
) -> None:
    pr = client.get("/api/v1/me/press-releases", headers=_auth(me_seed.token))
    assert pr.status_code == 200
    assert pr.get_json()["total"] == 1

    avis = client.get("/api/v1/me/enquiry-notices", headers=_auth(me_seed.token))
    assert avis.status_code == 200
    assert avis.get_json()["total"] == 1


def test_me_marketplace_lists_only_own(
    client: FlaskClient, me_seed: SimpleNamespace
) -> None:
    response = client.get("/api/v1/me/missions", headers=_auth(me_seed.token))
    assert response.status_code == 200
    items = response.get_json()["items"]
    titles = {item["title"] for item in items}
    assert "My mission" in titles
    assert "Not my mission" not in titles
    # The owner sees their own offer's contact email (it's theirs).
    mine = next(item for item in items if item["title"] == "My mission")
    assert mine["contact_email"] == "me@example.com"

    theirs = client.get(
        f"/api/v1/me/missions/{me_seed.other_mission.id}", headers=_auth(me_seed.token)
    )
    assert theirs.status_code == 404
