# Copyright (c) 2025, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only
"""Token-based authentication and scope enforcement for the public API.

This is the functional core of the API's security: pure helpers to mint,
hash and resolve tokens, plus thin accessors over the per-request identity
stored on Flask's ``g``. The imperative shell (the HTTP 401/403 wiring)
lives in ``__init__`` and ``resources``.
"""

from __future__ import annotations

import hashlib
import secrets
from enum import StrEnum

from flask import g
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.auth import User

from .models import ApiToken, _utcnow

# Human-facing prefix so a leaked string is recognisable as an AIpress24
# API token (helps secret-scanning tools flag it).
TOKEN_PREFIX = "a24_"  # noqa: S105 - a public identifier prefix, not a secret


class Scope(StrEnum):
    """Coarse, read-only capabilities a token may be granted."""

    READ_CONTENT = "read:content"  # articles, press releases, events
    READ_ORGANISATIONS = "read:organisations"  # organisations, business walls
    READ_DIRECTORY = "read:directory"  # personal member profiles


ALL_SCOPES: list[str] = [s.value for s in Scope]


def is_valid_scope(scope: str) -> bool:
    return scope in ALL_SCOPES


# --- token minting & hashing (pure) ---------------------------------------


def hash_token(raw_token: str) -> str:
    """Return the SHA-256 hex digest used as the token's storage key."""
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def generate_token() -> tuple[str, str, str]:
    """Mint a new secret.

    Returns a ``(raw_token, token_hash, token_prefix)`` triple. Only the
    hash and prefix are ever persisted; the raw token is shown once.
    """
    raw_token = TOKEN_PREFIX + secrets.token_urlsafe(32)
    return raw_token, hash_token(raw_token), raw_token[: len(TOKEN_PREFIX) + 6]


# --- token resolution (reads the DB, no writes) ---------------------------


def resolve_token(raw_token: str, session: Session) -> ApiToken | None:
    """Resolve a raw bearer token to a live, usable ``ApiToken``.

    Returns ``None`` for anything that must not authenticate: unknown token,
    revoked/expired token, or a token whose owner is inactive or a clone
    account. All failure modes collapse to ``None`` so callers cannot leak
    *why* a token was rejected.
    """
    if not raw_token:
        return None

    token = session.scalar(
        select(ApiToken).where(ApiToken.token_hash == hash_token(raw_token))
    )
    if token is None or not token.is_usable():
        return None

    user: User | None = token.user
    if user is None or not user.active or user.is_clone:
        return None

    return token


def parse_bearer_header(header_value: str | None) -> str:
    """Extract the raw token from an ``Authorization: Bearer <token>`` header."""
    if not header_value:
        return ""
    parts = header_value.split(None, 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return ""
    return parts[1].strip()


def touch(token: ApiToken) -> None:
    """Record that a token was just used (best-effort last-seen stamp)."""
    token.last_used_at = _utcnow()


# --- per-request identity (thin accessors over ``g``) ---------------------


def set_identity(token: ApiToken) -> None:
    g.api_token = token
    g.api_identity = token.user
    g.api_scopes = list(token.scopes or [])


def current_identity() -> User | None:
    return getattr(g, "api_identity", None)


def current_scopes() -> list[str]:
    return getattr(g, "api_scopes", [])


def has_scope(scope: str | Scope) -> bool:
    return str(scope) in current_scopes()
