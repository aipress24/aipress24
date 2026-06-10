# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from sqlalchemy import select
from werkzeug.exceptions import NotFound

from app.flask.extensions import db
from app.lib.base62 import base62


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
    stmt = select(cls).where(cls.id == id)  # type: ignore
    if options:
        stmt = stmt.options(options)
    result = db.session.execute(stmt)
    obj = result.scalar_one_or_none()
    if not obj:
        msg = f"Can't match id {id}"
        raise NotFound(msg)
    return obj


def get_multi(cls: type, stmt=None, options=None, limit: int | None = None) -> list:
    if stmt is None:
        stmt = select(cls)

    if options:
        stmt = stmt.options(options)

    if limit:
        stmt = stmt.limit(limit)

    result = db.session.execute(stmt)
    return list(result.scalars())
