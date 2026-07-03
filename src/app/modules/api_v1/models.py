# Copyright (c) 2025, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only
"""Persistent model for the public API's access tokens.

A token's plaintext secret is shown exactly once, at creation; only a
SHA-256 hash is stored, so a database leak never exposes usable tokens.
Each token is bound to a user, carries an explicit list of scopes, and can
be given an expiry and revoked independently of the user's web session.
"""

from __future__ import annotations

from datetime import UTC, datetime

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.auth import User
from app.models.base import Base


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _as_utc(value: datetime | None) -> datetime | None:
    """Normalise a stored datetime to timezone-aware UTC.

    SQLite drops tzinfo on read; Postgres keeps it. Treating a naive value
    as UTC makes validity comparisons behave identically on both backends.
    """
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value


class ApiToken(Base):
    """A hashed, scoped bearer token for third-party API access."""

    __tablename__ = "api_token"

    id: Mapped[int] = mapped_column(primary_key=True)

    # Human-readable label, e.g. "Acme newsroom integration".
    name: Mapped[str] = mapped_column(sa.String(120), default="")

    # SHA-256 hex digest of the secret. The secret itself is never stored.
    token_hash: Mapped[str] = mapped_column(sa.String(64), unique=True, index=True)
    # Non-secret leading fragment, shown in listings to identify a token.
    token_prefix: Mapped[str] = mapped_column(sa.String(16), default="")

    user_id: Mapped[int] = mapped_column(
        sa.ForeignKey(User.id), nullable=False, index=True
    )
    user: Mapped[User] = relationship(User, foreign_keys=[user_id])

    # Granted capabilities, e.g. ["read:content", "read:directory"].
    scopes: Mapped[list[str]] = mapped_column(sa.JSON, default=list)

    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), default=_utcnow
    )
    expires_at: Mapped[datetime | None] = mapped_column(
        sa.DateTime(timezone=True), nullable=True
    )
    last_used_at: Mapped[datetime | None] = mapped_column(
        sa.DateTime(timezone=True), nullable=True
    )
    revoked_at: Mapped[datetime | None] = mapped_column(
        sa.DateTime(timezone=True), nullable=True
    )

    def is_expired(self, now: datetime | None = None) -> bool:
        expires_at = _as_utc(self.expires_at)
        if expires_at is None:
            return False
        return (now or _utcnow()) >= expires_at

    def is_revoked(self) -> bool:
        return self.revoked_at is not None

    def is_usable(self, now: datetime | None = None) -> bool:
        """A token is usable when it is neither revoked nor expired."""
        return not self.is_revoked() and not self.is_expired(now)

    def has_scope(self, scope: str) -> bool:
        return scope in (self.scopes or [])

    def __repr__(self) -> str:
        return f"<ApiToken {self.token_prefix}… user={self.user_id}>"
