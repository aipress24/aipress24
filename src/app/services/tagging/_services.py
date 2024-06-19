# Copyright (c) 2021-2024 - Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

import sqlalchemy as sa

from app.flask.extensions import db

from ._models import TagApplication
from .interfaces import Taggable


def add_tag(obj: Taggable, label: str, type: str = "manual") -> TagApplication:
    # Prevent circular imports - Not sure how to do this better
    from app.models.content.textual import Article

    tag = TagApplication(type=type, label=label)

    # TODO
    match obj:
        case Article(id=id):
            tag.object_id = id
        case _:  # pragma: no cover
            raise NotImplementedError

    return tag


def get_tag_applications(obj) -> list[TagApplication]:
    # type = obj.__class__.__name__.lower()
    # object_id = f"{type}:{obj.id}"
    object_id = obj.id
    stmt = (
        sa.select(TagApplication)
        .where(TagApplication.object_id == object_id)
        .order_by(TagApplication.label)
    )
    return list(db.session.scalars(stmt))


def get_tags(obj) -> list:
    tag_applications = get_tag_applications(obj)
    d = {}
    for ta in tag_applications:
        if ta.label not in d:
            d[ta.label] = {"label": ta.label, "type": ta.type}
            continue
        if ta.type == "auto":
            continue
        d[ta.label]["type"] = "manual"

    # l = list(d.items())
    # l.sort()
    return [t[1] for t in sorted(d.items())]
