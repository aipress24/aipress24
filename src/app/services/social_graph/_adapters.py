# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from functools import singledispatch
from typing import Never, TypeAlias, Union

import sqlalchemy as sa
from attr import define

from app.flask.extensions import db
from app.lib import adapter
from app.lib.adapter import Adapter
from app.models.auth import User

# Import both BaseContent classes (legacy architecture has two different ones)
from app.models.base_content import BaseContent as FrontendBaseContent
from app.models.content.base import BaseContent as ContentBaseContent
from app.models.organisation import Organisation
from app.modules.events.models import EventPost
from app.services.activity_stream import ActivityType, post_activity

from .models import following_orgs_table, following_users_table, likes_table

Followable: TypeAlias = Union[User, Organisation, "SocialUser", "SocialOrganisation"]


class SocialGraphError(Exception):
    pass


class FollowableAdapter(Adapter):
    @property
    def _obj(self) -> User | Organisation:
        return self._get_adaptee()

    def get_followers(self, order_by=None, limit=0) -> list[User]:
        match self._obj:
            case User():
                table = following_users_table
            case Organisation():
                table = following_orgs_table
            case _:
                raise ValueError

        stmt1 = sa.select(table.c.follower_id).where(
            table.c.followee_id == self._obj.id
        )
        ids = db.session.scalars(stmt1)

        stmt2 = sa.select(User).where(User.id.in_(ids))
        if order_by is not None:
            stmt2 = stmt2.order_by(order_by)
        if limit:
            stmt2 = stmt2.limit(limit)

        return list(db.session.scalars(stmt2))

    def num_followers(self):
        match self._obj:
            case User():
                table = following_users_table
            case Organisation():
                table = following_orgs_table
            case _:
                raise ValueError

        stmt = sa.select(sa.func.count()).where(table.c.followee_id == self._obj.id)
        return db.session.scalar(stmt)


class LikeableMixin:
    content: FrontendBaseContent | ContentBaseContent

    def num_likes(self):
        stmt = sa.select(sa.func.count()).where(
            likes_table.c.content_id == self.content.id
        )
        return db.session.scalar(stmt)


@define
class SocialUser(FollowableAdapter):
    user: User

    _adaptee_id = "user"

    #
    # Following
    #
    def is_following(self, object: Followable) -> bool:
        # assert isinstance(object, Followable)

        match object:
            case User() | SocialUser():
                table = following_users_table
            case Organisation() | SocialOrganisation():
                table = following_orgs_table
            case _:
                raise ValueError

        stmt = sa.select(table).where(
            table.c.followee_id == object.id, table.c.follower_id == self.id
        )
        rows = db.session.execute(stmt)
        return len(list(rows)) == 1

    def get_followees(
        self, cls: type = User, order_by=None, limit=0
    ) -> list[User | Organisation]:
        assert cls in {User, Organisation}

        if cls is User:
            table = following_users_table
        elif cls is Organisation:
            table = following_orgs_table
        else:
            raise ValueError

        stmt1 = sa.select(table.c.followee_id).where(table.c.follower_id == self.id)
        ids = db.session.scalars(stmt1)

        stmt2: sa.Select = sa.select(cls).where(cls.id.in_(ids))
        if order_by is not None:
            stmt2 = stmt2.order_by(order_by)
        if limit:
            stmt2 = stmt2.limit(limit)

        return list(db.session.scalars(stmt2))

    def num_followees(self, cls: type = User) -> int:
        assert cls in {User, Organisation}

        if cls is User:
            table = following_users_table
        elif cls is Organisation:
            table = following_orgs_table
        else:  # pragma: no cover
            raise ValueError

        stmt = sa.select(sa.func.count()).where(table.c.follower_id == self.user.id)
        return db.session.scalar(stmt) or 0

    def follow(self, object: Followable) -> None:
        match object:
            case User() | SocialUser():
                table = following_users_table
            case Organisation() | SocialOrganisation():
                table = following_orgs_table
            case _:  # pragma: no cover
                raise ValueError

        subject = self.user
        if subject == object:
            msg = "User can't follow themself"
            raise SocialGraphError(msg)

        stmt = sa.insert(table).values(followee_id=object.id, follower_id=subject.id)
        db.session.execute(stmt)

        post_activity(ActivityType.Follow, unadapt(subject), unadapt(object))  # type: ignore[arg-type]

    def unfollow(self, object: Followable) -> None:
        subject = self.user
        match object:
            case User() | SocialUser():
                table = following_users_table
            case Organisation() | SocialOrganisation():
                table = following_orgs_table
            case _:  # pragma: no cover
                raise ValueError

        stmt = sa.delete(table).where(
            table.c.followee_id == object.id, table.c.follower_id == subject.id
        )
        db.session.execute(stmt)

        post_activity(ActivityType.Unfollow, unadapt(subject), unadapt(object))  # type: ignore[arg-type]

    #
    # Likes
    #
    def is_liking(
        self, content: FrontendBaseContent | ContentBaseContent | SocialContent
    ) -> bool:
        content_id = (
            content.id
            if isinstance(content, (FrontendBaseContent, ContentBaseContent))
            else content.content.id
        )
        stmt = sa.select(likes_table).where(
            likes_table.c.user_id == self.user.id,
            likes_table.c.content_id == content_id,
        )
        rows = db.session.execute(stmt)
        return len(list(rows)) == 1

    def like(
        self, content: FrontendBaseContent | ContentBaseContent | SocialContent
    ) -> None:
        if self.is_liking(content):
            return

        content_id = (
            content.id
            if isinstance(content, (FrontendBaseContent, ContentBaseContent))
            else content.content.id
        )
        stmt = sa.insert(likes_table).values(
            user_id=self.user.id, content_id=content_id
        )
        db.session.execute(stmt)

    def unlike(
        self, content: FrontendBaseContent | ContentBaseContent | SocialContent
    ) -> None:
        if not self.is_liking(content):
            return

        content_id = (
            content.id
            if isinstance(content, (FrontendBaseContent, ContentBaseContent))
            else content.content.id
        )
        stmt = sa.delete(likes_table).where(
            likes_table.c.user_id == self.user.id,
            likes_table.c.content_id == content_id,
        )
        db.session.execute(stmt)


@define
class SocialOrganisation(FollowableAdapter, LikeableMixin):
    org: Organisation

    _adaptee_id = "org"

    def __attrs_post_init__(self):
        assert isinstance(self.org, Organisation)


@define
class SocialContent(Adapter, LikeableMixin):
    content: FrontendBaseContent | ContentBaseContent
    _adaptee_id = "content"

    def __attrs_post_init__(self):
        # Support both BaseContent hierarchies (legacy architecture)
        assert isinstance(self.content, (FrontendBaseContent, ContentBaseContent))


@singledispatch
def adapt(obj) -> Never:
    msg = f"Adaptation of {obj} (of type {type(obj)} not implemented"
    raise NotImplementedError(msg)


@adapt.register
def adapt_user(user: User) -> SocialUser:
    return adapter.adapt(user, SocialUser)


@adapt.register
def adapt_org(org: Organisation) -> SocialOrganisation:
    return adapter.adapt(org, SocialOrganisation)


@adapt.register
def adapt_frontend_post(content: FrontendBaseContent) -> SocialContent:
    return adapter.adapt(content, SocialContent)


@adapt.register
def adapt_content_post(content: ContentBaseContent) -> SocialContent:
    return adapter.adapt(content, SocialContent)


@adapt.register
def adapt_event_post(event: EventPost) -> SocialContent:
    return adapter.adapt(event, SocialContent)


unadapt = adapter.unadapt
