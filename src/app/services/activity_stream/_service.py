# Copyright (c) 2021-2024 - Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

import sqlalchemy as sa
from flask_super.decorators import service

from app.flask.extensions import db
from app.flask.routing import url_for
from app.models.auth import User
from app.models.organisation import Organisation
from app.modules.swork.models import Group

from ._models import Activity, ActivityType


@service
class ActivityStream:
    def post_activity(
        self, type: ActivityType, actor: User, object=None, target=None
    ) -> Activity:
        return post_activity(type, actor, object, target)

    def get_timeline(
        self, *, actor=None, object=None, limit=10
    ) -> list[tuple[Activity, str]]:
        return get_timeline(actor=actor, object=object, limit=limit)


def post_activity(
    type: ActivityType, actor: User, object=None, target=None
) -> Activity:
    assert isinstance(type, ActivityType)
    assert isinstance(actor, User)

    activity = Activity()
    activity.type = type

    activity.actor_id = actor.id
    activity.actor_url = url_for(actor, _external=False)
    activity.actor_name = actor.name

    if object:
        activity.object_id = object.id
        activity.object_type = _get_type(object)
        activity.object_url = url_for(object, _external=False)
        activity.object_name = object.name

    if target:
        activity.target_id = target.id
        activity.target_type = _get_type(target)
        activity.target_url = url_for(target, _external=False)
        activity.target_name = target.name

    db.session.add(activity)

    # Needed ?
    return activity


def get_timeline(*, actor=None, object=None, limit=10) -> list[tuple[Activity, str]]:
    if not actor and not object:
        raise Exception

    if actor:
        stmt = (
            sa.select(Activity)
            .where(Activity.actor_id == actor.id)
            .order_by(Activity.timestamp.desc())
        )

    elif object:
        stmt = (
            sa.select(Activity)
            .where(
                Activity.object_id == object.id,
                Activity.object_type == _get_type(object),
            )
            .order_by(Activity.timestamp.desc())
        )

    else:
        # Should never happen
        return []

    stmt = stmt.limit(limit)
    activities = list(db.session.execute(stmt).scalars())
    return [(activity, _get_msg(activity)) for activity in activities]


def _get_type(obj) -> str:
    match obj:
        case Group():
            return "Group"

        case Organisation():
            return "Organisation"

        case User():
            return "User"

        case _:
            raise TypeError(f"Uknown object type: {type(obj)}")


def _get_msg(activity: Activity) -> str:
    actor_name = activity.actor_name
    object_name = activity.object_name
    object_type = activity.object_type

    msg = ""

    match activity.type, object_type:
        case [ActivityType.Join, "Group"]:
            msg = f"{actor_name} a rejoint le groupe {object_name}"
        case [ActivityType.Leave, "Group"]:
            msg = f"{actor_name} a quitté le groupe {object_name}"

        case [ActivityType.Follow, _]:
            msg = f"{actor_name} suit à présent {object_name}"
        case [ActivityType.Unfollow, _]:
            msg = f"{actor_name} ne suit plus {object_name}"

        case [_, _]:
            raise TypeError(f"Uknown activity type: {activity.type}/{object_type}")

    return msg
