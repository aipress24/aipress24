# Copyright (c) 2025, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only
"""Integration tests for token resolution against the database.

These use flush-only fixtures (no commit) so the transaction-wrapped
``db_session`` rolls everything back — see the tier's conftest.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.models.auth import User
from app.modules.api_v1.models import ApiToken
from app.modules.api_v1.security import ALL_SCOPES, generate_token, resolve_token


def _user(db_session: Session, *, active: bool = True, is_clone: bool = False) -> User:
    user = User(
        email=f"u-{uuid.uuid4().hex[:8]}@example.com",
        active=active,
        is_clone=is_clone,
    )
    db_session.add(user)
    db_session.flush()
    return user


def _token(db_session: Session, user: User, **kwargs) -> tuple[str, ApiToken]:
    raw, digest, prefix = generate_token()
    token = ApiToken(
        token_hash=digest,
        token_prefix=prefix,
        user_id=user.id,
        scopes=list(ALL_SCOPES),
        **kwargs,
    )
    db_session.add(token)
    db_session.flush()
    return raw, token


def test_resolve_valid_token(db_session: Session) -> None:
    user = _user(db_session)
    raw, token = _token(db_session, user)
    assert resolve_token(raw, db_session) is token


def test_resolve_unknown_token(db_session: Session) -> None:
    assert resolve_token("a24_does-not-exist", db_session) is None
    assert resolve_token("", db_session) is None


def test_resolve_revoked_token(db_session: Session) -> None:
    user = _user(db_session)
    raw, _ = _token(db_session, user, revoked_at=datetime.now(UTC))
    assert resolve_token(raw, db_session) is None


def test_resolve_expired_token(db_session: Session) -> None:
    user = _user(db_session)
    raw, _ = _token(db_session, user, expires_at=datetime.now(UTC) - timedelta(days=1))
    assert resolve_token(raw, db_session) is None


def test_resolve_rejects_inactive_user(db_session: Session) -> None:
    user = _user(db_session, active=False)
    raw, _ = _token(db_session, user)
    assert resolve_token(raw, db_session) is None


def test_resolve_rejects_clone_user(db_session: Session) -> None:
    user = _user(db_session, is_clone=True)
    raw, _ = _token(db_session, user)
    assert resolve_token(raw, db_session) is None
