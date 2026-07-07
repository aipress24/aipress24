# Copyright (c) 2025, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only
"""Unit tests for the API's pure logic: serialization, links, tokens."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any

from app.modules.api_v1.models import ApiToken
from app.modules.api_v1.schemas import ArticleSchema, MemberSchema, page_links
from app.modules.api_v1.security import (
    TOKEN_PREFIX,
    generate_token,
    hash_token,
    is_valid_scope,
    parse_bearer_header,
)


def _article() -> SimpleNamespace:
    return SimpleNamespace(
        id=123,
        title="T",
        summary="s",
        content="<p>c</p>",
        genre="",
        section="",
        topic="",
        sector="",
        language="fr",
        geo_localisation="",
        pays_zip_ville="",
        published_at=None,
        last_updated_at=None,
        expires_at=None,
        view_count=1,
        like_count=2,
        comment_count=3,
        publisher_id=55,
        media_id=None,
        # PII that must never be serialized:
        owner_id=999,
        rights_sales_snapshot={"x": 1},
        newsroom_id=42,
    )


def test_article_schema_allowlist_and_links() -> None:
    # marshmallow's `dump()` is typed loosely (a list-ish union); for a single
    # object it returns a dict — annotate so the key access below type-checks.
    out: dict[str, Any] = ArticleSchema().dump(_article())

    assert out["id"] == 123
    assert out["kind"] == "article"
    assert out["_links"]["self"]["href"] == "/api/v1/articles/123"
    assert out["_links"]["publisher"]["href"] == "/api/v1/organisations/55"
    assert "media" not in out["_links"]  # media_id is None

    for leaked in ("owner_id", "rights_sales_snapshot", "newsroom_id"):
        assert leaked not in out


def test_member_schema_redacts_pii() -> None:
    member = SimpleNamespace(
        id=7,
        first_name="A",
        last_name="B",
        full_name="A B",
        gender="?",
        status="",
        karma=0.0,
        job_title="",
        organisation_name="",
        organisation_id=None,
        profile=None,
        # PII:
        email="secret@example.com",
        tel_mobile="0600000000",
        password="hash",
        fs_uniquifier="uniq",
        is_clone=False,
    )
    member.photo_image_signed_url = lambda *a, **k: "/img.png"

    out: dict[str, Any] = MemberSchema().dump(member)

    for leaked in ("email", "tel_mobile", "password", "fs_uniquifier", "is_clone"):
        assert leaked not in out
    assert out["_links"]["self"]["href"] == "/api/v1/members/7"
    assert out["metiers"] == []  # profile is None -> safe default


def test_page_links() -> None:
    middle = page_links("articles", limit=10, offset=10, total=100)
    assert middle["self"]["href"] == "/api/v1/articles?limit=10&offset=10"
    assert middle["prev"]["href"] == "/api/v1/articles?limit=10&offset=0"
    assert middle["next"]["href"] == "/api/v1/articles?limit=10&offset=20"

    single = page_links("articles", limit=10, offset=0, total=5)
    assert "prev" not in single
    assert "next" not in single


def test_token_helpers() -> None:
    raw, digest, prefix = generate_token()
    assert raw.startswith(TOKEN_PREFIX)
    assert hash_token(raw) == digest
    assert prefix == raw[: len(TOKEN_PREFIX) + 6]

    assert parse_bearer_header(f"Bearer {raw}") == raw
    assert parse_bearer_header(f"bearer {raw}") == raw  # case-insensitive scheme
    assert parse_bearer_header("Basic abc") == ""
    assert parse_bearer_header(None) == ""

    assert is_valid_scope("read:content")
    assert not is_valid_scope("write:everything")


def test_apitoken_validity() -> None:
    now = datetime(2025, 1, 1, tzinfo=UTC)
    token = ApiToken(token_hash="x", user_id=1, scopes=["read:content"])
    token.expires_at = None
    token.revoked_at = None
    assert token.is_usable(now)

    token.expires_at = now - timedelta(days=1)
    assert not token.is_usable(now)

    token.expires_at = None
    token.revoked_at = now
    assert not token.is_usable(now)

    assert token.has_scope("read:content")
    assert not token.has_scope("read:directory")
