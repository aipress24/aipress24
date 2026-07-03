# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from typing import Any, Protocol, cast

from flask import g
from sqlalchemy import select
from sqlalchemy.orm import Mapped
from werkzeug.exceptions import NotFound

from app.enums import RoleEnum
from app.flask.extensions import db
from app.lib.base62 import base62
from app.models.lifecycle import PublicationStatus


class _HasId(Protocol):
    id: Mapped[Any]


def parse_id(id: int | str) -> int:
    """Normalise an id-like input to an int.

    Strings starting with "x" are treated as base62-encoded ids, other
    strings are parsed as plain decimal integers. Anything that fails to
    parse raises ``NotFound`` so callers don't have to wrap the call.
    """
    match id:
        case str():
            try:
                if id.startswith("x"):
                    return base62.decode(id)
                return int(id)
            except (ValueError, TypeError):
                # Non-numeric / non-base62 string — treat as a
                # 404 rather than letting a 500 escape (crawlers,
                # truncated URL pastes, scanner fuzz).
                msg = f"Can't match id {id}"
                raise NotFound(msg) from None
        case int():
            return id
        case _:
            msg = f"Can't match id {id}"
            raise NotFound(msg)


def get_obj(id: int | str, cls: type, options=None):
    id = parse_id(id)
    m = cast("type[_HasId]", cls)
    stmt = select(m).where(m.id == id)
    if options:
        stmt = stmt.options(options)
    result = db.session.execute(stmt)
    obj = result.scalar_one_or_none()
    if not obj:
        msg = f"Can't match id {id}"
        raise NotFound(msg)
    return obj


def get_public_obj(id: int | str, cls: type, options=None):
    """Like :func:`get_obj`, but 404 a non-public content row.

    A public content-detail page must not serve DRAFT / unpublished / taken-down
    content (only status==PUBLIC rows appear in the portal listings). Access
    parity is preserved: the current user can still reach their *own* not-yet-
    public content, and admins can reach any (for moderation); everyone else
    gets a 404, exactly as if the row did not exist.
    """
    obj = get_obj(id, cls, options=options)
    if getattr(obj, "status", None) == PublicationStatus.PUBLIC:
        return obj

    user = getattr(g, "user", None)
    if user is not None and not user.is_anonymous:
        from app.services.roles import has_role

        if getattr(obj, "owner_id", None) == user.id or has_role(user, RoleEnum.ADMIN):
            return obj

    msg = f"Not public: {id}"
    raise NotFound(msg)


def get_multi(cls: type, stmt=None, options=None, limit: int | None = None) -> list:
    if stmt is None:
        stmt = select(cls)

    if options:
        stmt = stmt.options(options)

    if limit:
        stmt = stmt.limit(limit)

    result = db.session.execute(stmt)
    return list(result.scalars())
