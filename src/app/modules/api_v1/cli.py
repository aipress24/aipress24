# Copyright (c) 2025, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only
"""``flask api-token …`` CLI to issue, list and revoke public-API tokens.

Tokens are the only way third parties authenticate against ``/api/v1``.
Issuing prints the secret exactly once — it is stored only as a hash.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import click
from flask.cli import with_appcontext
from flask_super.cli import group
from rich import print
from sqlalchemy import select

from app.flask.extensions import db
from app.models.auth import User

from .models import ApiToken
from .security import ALL_SCOPES, generate_token, is_valid_scope


@group(short_help="Manage public API (/api/v1) access tokens")
def api_token() -> None:
    pass


@api_token.command(short_help="Issue a new token for a user")
@click.option("--email", required=True, help="Owner's login email.")
@click.option("--name", default="", help="Human-readable label for the token.")
@click.option(
    "--scopes",
    default=",".join(ALL_SCOPES),
    help=f"Comma-separated scopes. Available: {', '.join(ALL_SCOPES)}.",
)
@click.option(
    "--expires-days",
    type=int,
    default=None,
    help="Optional lifetime in days (default: no expiry).",
)
@with_appcontext
def issue(email: str, name: str, scopes: str, expires_days: int | None) -> None:
    user = db.session.scalar(select(User).where(User.email == email))
    if user is None:
        msg = f"No user with email {email!r}."
        raise click.ClickException(msg)
    if not user.active or user.is_clone:
        msg = f"User {email!r} is inactive or a clone account."
        raise click.ClickException(msg)

    requested = [s.strip() for s in scopes.split(",") if s.strip()]
    invalid = [s for s in requested if not is_valid_scope(s)]
    if invalid:
        msg = (
            f"Unknown scope(s): {', '.join(invalid)}. "
            f"Available: {', '.join(ALL_SCOPES)}."
        )
        raise click.ClickException(msg)

    raw_token, token_hash, token_prefix = generate_token()
    expires_at = (
        datetime.now(UTC) + timedelta(days=expires_days) if expires_days else None
    )
    token = ApiToken(
        name=name,
        token_hash=token_hash,
        token_prefix=token_prefix,
        user_id=user.id,
        scopes=requested,
        expires_at=expires_at,
    )
    db.session.add(token)
    db.session.commit()

    print(f"[green]Issued token #{token.id}[/green] for [cyan]{email}[/cyan]")
    print(f"  scopes : {', '.join(requested)}")
    print(f"  expires: {expires_at.isoformat() if expires_at else 'never'}")
    print(
        "\n[bold yellow]Copy this token now — it will not be shown again:[/bold yellow]"
    )
    print(f"[bold]{raw_token}[/bold]\n")


@api_token.command(name="list", short_help="List tokens")
@click.option("--email", default=None, help="Filter by owner email.")
@with_appcontext
def list_tokens(email: str | None) -> None:
    stmt = select(ApiToken).order_by(ApiToken.id)
    if email:
        stmt = stmt.join(User).where(User.email == email)
    tokens = list(db.session.scalars(stmt))
    if not tokens:
        print("[yellow]No tokens found.[/yellow]")
        return
    for token in tokens:
        state = "revoked" if token.is_revoked() else "active"
        owner = token.user.email if token.user else f"user#{token.user_id}"
        # token.scopes is Mapped[list[str]]; pyrefly mis-types the instance
        # access as the descriptor, so join() looks like a bad overload.
        # pyrefly: ignore [no-matching-overload]
        scopes = ", ".join(token.scopes or [])
        print(
            f"  #[cyan]{token.id}[/cyan] {token.token_prefix}… "
            f"[{state}] {owner} :: {scopes} "
            f":: {token.name or '(no name)'}"
        )


@api_token.command(short_help="Revoke a token by id")
@click.argument("token_id", type=int)
@with_appcontext
def revoke(token_id: int) -> None:
    token = db.session.get(ApiToken, token_id)
    if token is None:
        msg = f"No token with id {token_id}."
        raise click.ClickException(msg)
    if token.is_revoked():
        print(f"[yellow]Token #{token_id} was already revoked.[/yellow]")
        return
    token.revoked_at = datetime.now(UTC)
    db.session.commit()
    print(f"[green]Revoked token #{token_id}.[/green]")
