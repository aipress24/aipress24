# Copyright (c) 2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only
"""Issuing, listing and revoking API tokens."""

from __future__ import annotations

from datetime import datetime, timedelta

import sqlalchemy as sa
from sqlalchemy.orm import Session, joinedload

from app.models.auth import User

from .models import ApiToken, _utcnow
from .security import Scope, generate_token

MAX_NAME_LENGTH = 120
MAX_ACTIVE_TOKENS = 10
# Lifetimes a member may choose: their tokens always expire.
LIFETIMES = (30, 90, 365)

# Scopes members may grant themselves. The directory is left out, as it lets
# a program copy every member's profile: an administrator issues those tokens.
MEMBER_SCOPES: dict[str, str] = {
    Scope.READ_SELF: "Lire mon profil et mes propres contenus, brouillons compris",
    Scope.WRITE_CONTENT: "Créer, modifier, publier et supprimer mes contenus",
    Scope.READ_CONTENT: "Lire les articles, communiqués et événements publiés",
    Scope.READ_ORGANISATIONS: "Lire les organisations et les Business Walls",
}


class TokenRefusedError(Exception):
    """A token request a member may not make; the message is shown to them."""


def issue_member_token(
    session: Session, user: User, name: str, scopes: list[str], days: int | None
) -> str:
    """Issue a token a member asked for, and return its secret."""
    name = name.strip()
    if not name or len(name) > MAX_NAME_LENGTH:
        msg = f"Donnez un nom à la clé ({MAX_NAME_LENGTH} caractères au plus)."
        raise TokenRefusedError(msg)
    if not scopes or not set(scopes) <= MEMBER_SCOPES.keys():
        msg = "Choisissez au moins un droit dans la liste."
        raise TokenRefusedError(msg)
    if days not in LIFETIMES:
        msg = "Choisissez une durée dans la liste."
        raise TokenRefusedError(msg)
    if len(active_tokens(session, user)) >= MAX_ACTIVE_TOKENS:
        msg = f"Vous avez déjà {MAX_ACTIVE_TOKENS} clés actives : révoquez-en une."
        raise TokenRefusedError(msg)
    _token, secret = issue_token(
        session, user, name, scopes, _utcnow() + timedelta(days=days)
    )
    return secret


def issue_token(
    session: Session,
    user: User,
    name: str,
    scopes: list[str],
    expires_at: datetime | None,
) -> tuple[ApiToken, str]:
    """Add a token for ``user``, and return it with its secret."""
    secret, token_hash, token_prefix = generate_token()
    token = ApiToken(
        name=name,
        token_hash=token_hash,
        token_prefix=token_prefix,
        user_id=user.id,
        scopes=scopes,
        expires_at=expires_at,
    )
    session.add(token)
    return token, secret


def active_tokens(session: Session, user: User | None = None) -> list[ApiToken]:
    """The usable tokens of a user, or of everybody, newest first."""
    stmt = (
        sa.select(ApiToken)
        .where(
            ApiToken.revoked_at.is_(None),
            sa.or_(ApiToken.expires_at.is_(None), ApiToken.expires_at > _utcnow()),
        )
        .options(joinedload(ApiToken.user))
        .order_by(ApiToken.id.desc())
    )
    if user is not None:
        stmt = stmt.where(ApiToken.user_id == user.id)
    return list(session.scalars(stmt))


def revoke_token(token: ApiToken) -> None:
    """Revoke a token for good, keeping the date of a first revocation."""
    token.revoked_at = token.revoked_at or _utcnow()
