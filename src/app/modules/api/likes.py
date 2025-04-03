# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from flask import g

from app.flask.extensions import db
from app.flask.sqla import get_obj
from app.modules.swork.models import ShortPost as Post
from app.services.social_graph import adapt

from . import blueprint


@blueprint.post("/likes/<cls>/<id>")
def likes(cls: str, id: int) -> str:
    # Assume action == "toggle" for now
    # Assume cls == "post" for now

    obj = get_obj(id, Post)
    return toggle_like(obj)


def toggle_like(obj: Post) -> str:
    user = adapt(g.user)
    if user.is_liking(obj):
        user.unlike(obj)
    else:
        user.like(obj)
    db.session.flush()
    obj.like_count = adapt(obj).num_likes()
    db.session.commit()
    return str(obj.like_count)
