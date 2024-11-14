# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from sqlalchemy import select
from werkzeug.exceptions import NotFound

from app.flask.extensions import db
from app.lib.base62 import base62


def get_obj(id: int | str, cls: type, options=None):
    match id:
        case str():
            if id.startswith("x"):
                id = base62.decode(id)
            else:
                id = int(id)
        case int():
            pass
        case _:
            msg = f"Can't match id {id}"
            raise NotFound(msg)

    stmt = select(cls).where(cls.id == id)  # type: ignore
    if options:
        stmt = stmt.options(options)
    result = db.session.execute(stmt)
    obj = result.scalar_one_or_none()
    if not obj:
        raise NotFound
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
