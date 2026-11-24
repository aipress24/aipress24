# Copyright (c) 2025, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only
"""Fixtures for the public-API HTTP tests (c_e2e tier, fresh_db).

The API commits (a ``last_used_at`` stamp on auth), so its round-trip tests
live here rather than in b_integration. Data is committed so that the
separate request context created by the test client can see it.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import arrow
import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.enums import RoleEnum
from app.models.auth import Role, User
from app.models.lifecycle import PublicationStatus
from app.models.organisation import Organisation
from app.modules.api_v1.models import ApiToken
from app.modules.api_v1.security import ALL_SCOPES, Scope, generate_token
from app.modules.events.models import EventPost
from app.modules.wire.models import ArticlePost
from app.services.taxonomies import TaxonomyEntry

# A body long enough that truncate_body(300) cuts before the tail marker.
PAID_BODY_TAIL = "ENDOFBODYMARKER"
PAID_ARTICLE_BODY = (
    "<p>" + ("lorem ipsum dolor sit amet " * 30) + PAID_BODY_TAIL + "</p>"
)


CLASSIFICATION = {
    "genre": "Annonce produit",
    "section": "Économie",
    "topic": "Innovation",
    "sector": "Industrie",
}
_VOCABULARIES = {
    "genre": "genres-com",
    "section": "sections",
    "topic": "topics",
    "sector": "news_sectors",
}


@pytest.fixture
def press_vocabularies(db_session: Session) -> None:
    """The values a press release may be classified under."""
    db_session.add_all(
        TaxonomyEntry(
            name=CLASSIFICATION[field],
            value=CLASSIFICATION[field],
            category="",
            seq=1,
            taxonomy_name=taxonomy,
        )
        for field, taxonomy in _VOCABULARIES.items()
    )
    db_session.commit()


def _email() -> str:
    return f"api-{uuid.uuid4().hex[:8]}@example.com"


def _mint_token(db_session: Session, user: User, scopes: list[str]) -> str:
    raw, digest, prefix = generate_token()
    token = ApiToken(
        name="test token",
        token_hash=digest,
        token_prefix=prefix,
        user_id=user.id,
        scopes=list(scopes),
    )
    db_session.add(token)
    db_session.commit()
    return raw


@pytest.fixture
def seed(db_session: Session) -> SimpleNamespace:
    role = Role(name=RoleEnum.PRESS_MEDIA.name, description=RoleEnum.PRESS_MEDIA.value)
    org = Organisation(name=f"Acme {uuid.uuid4().hex[:6]}")
    user = User(email=_email(), first_name="Jane", last_name="Doe", active=True)
    user.roles.append(role)
    user.organisation = org
    reader = User(email=_email(), first_name="Rick", last_name="Reader", active=True)
    db_session.add_all([role, org, user, reader])
    db_session.flush()

    now = datetime.now(UTC)
    published_1 = ArticlePost(
        owner=user,
        title="Public 1",
        content="<p>a</p>",
        summary="s1",
        status=PublicationStatus.PUBLIC,
        published_at=now,
    )
    published_2 = ArticlePost(
        owner=user,
        title="Public 2",
        content="<p>b</p>",
        summary="s2",
        status=PublicationStatus.PUBLIC,
        published_at=now,
    )
    draft = ArticlePost(
        owner=user,
        title="Draft",
        content="<p>d</p>",
        summary="sd",
        status=PublicationStatus.DRAFT,
    )
    # PUBLIC but past its expiry -> must be excluded (matches is_public).
    expired = ArticlePost(
        owner=user,
        title="Expired",
        content="<p>e</p>",
        summary="se",
        status=PublicationStatus.PUBLIC,
        published_at=now,
        expires_at=now - timedelta(days=1),
    )
    event = EventPost(
        owner=user,
        title="Expo",
        content="<p>ev</p>",
        summary="sev",
        status=PublicationStatus.PUBLIC,
        published_at=arrow.utcnow(),
    )
    draft_event = EventPost(
        owner=user,
        title="Hidden expo",
        content="<p>h</p>",
        summary="sh",
        status=PublicationStatus.DRAFT,
    )
    long_article = ArticlePost(
        owner=user,
        title="Long body",
        content=PAID_ARTICLE_BODY,
        summary="long",
        status=PublicationStatus.PUBLIC,
        published_at=now,
    )
    db_session.add_all(
        [published_1, published_2, draft, expired, event, draft_event, long_article]
    )
    db_session.commit()

    full_token = _mint_token(db_session, user, ALL_SCOPES)
    content_only_token = _mint_token(db_session, user, [Scope.READ_CONTENT.value])
    reader_token = _mint_token(db_session, reader, ALL_SCOPES)

    return SimpleNamespace(
        user=user,
        org=org,
        reader=reader,
        published_1=published_1,
        published_2=published_2,
        draft=draft,
        expired=expired,
        event=event,
        draft_event=draft_event,
        long_article=long_article,
        token=full_token,
        content_only_token=content_only_token,
        reader_token=reader_token,
    )


@pytest.fixture
def auth(seed: SimpleNamespace) -> dict[str, str]:
    return {"Authorization": f"Bearer {seed.token}"}


def _role(db_session: Session, name: RoleEnum) -> Role:
    """Get-or-create: role names are globally unique and may be pre-seeded."""
    existing = db_session.scalar(select(Role).where(Role.name == name.name))
    if existing:
        return existing
    role = Role(name=name.name, description=name.value)
    db_session.add(role)
    db_session.flush()
    return role


@pytest.fixture
def wseed(db_session: Session, press_vocabularies: None) -> SimpleNamespace:
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
        author_token=_mint_token(db_session, author, ALL_SCOPES),
        author_read_only=_mint_token(db_session, author, [Scope.READ_SELF.value]),
        journalist_token=_mint_token(db_session, journalist, ALL_SCOPES),
        other_token=_mint_token(db_session, other, ALL_SCOPES),
    )
