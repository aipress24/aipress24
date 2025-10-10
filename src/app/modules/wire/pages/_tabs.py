# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

import abc
from operator import itemgetter

import sqlalchemy as sa
from flask import g, session
from pipe import groupby
from sqlalchemy.orm import selectinload

from app.enums import OrganisationTypeEnum
from app.flask.sqla import get_multi
from app.models.auth import User
from app.models.lifecycle import PublicationStatus
from app.models.organisation import Organisation
from app.modules.wire.models import Post
from app.services.social_graph import adapt

from ._filters import FilterBar


def get_tabs():
    return [
        WallTab(),
        AgenciesTab(),
        MediasTab(),
        JournalistsTab(),
        ComTab(),
    ]


class Tab(abc.ABC):
    id: str
    label: str
    tip: str

    @property
    def is_active(self):
        return session["wire:tab"] == self.id

    def get_posts(self, filter_bar: FilterBar):
        stmt = self.get_stmt(filter_bar)

        authors = self.get_authors()
        if authors is not None:
            author_ids = [f.id for f in authors]
            stmt = stmt.where(Post.owner_id.in_(author_ids))

        posts = get_multi(Post, stmt)
        return posts

    def get_authors(self) -> list[User] | None:
        """Override in subclasses to filter by certain authors."""
        return None

    def get_stmt(self, filter_bar: FilterBar):
        active_filters = filter_bar.active_filters
        sort_order = filter_bar.sort_order

        match sort_order:
            case "likes":
                order = Post.like_count.desc()
            case "comments":
                order = Post.comment_count.desc()
            case _:
                order = Post.published_at.desc()

        stmt = (
            sa.select(Post)
            .where(Post.status == PublicationStatus.PUBLIC)
            .order_by(order)
            .options(selectinload(Post.owner))
            .limit(30)
        )

        for filter_id, filter_values in active_filters | groupby(itemgetter("id")):
            # FIXME
            if filter_id == "tag":
                continue
            if not hasattr(Post, filter_id):
                continue
            values = [filter["value"] for filter in filter_values]
            where_clause = getattr(Post, filter_id).in_(values)
            stmt = stmt.where(where_clause)

        return stmt


class WallTab(Tab):
    id = "wall"
    label = "All"
    tip = "Fil d'actus"

    def get_authors(self) -> None:
        return None


class AgenciesTab(Tab):
    id = "agencies"
    label = "Agences"
    tip = "Agences de Presse"

    def get_authors(self):
        orgs: list[Organisation] = adapt(g.user).get_followees(cls=Organisation)
        journalists = set()
        for org in orgs:
            if org.type == OrganisationTypeEnum.AGENCY:
                journalists.update(list(org.members))
        return journalists


class MediasTab(Tab):
    id = "media"
    label = "Médias"
    tip = "Médias (presse, en ligne...) auxquels je suis abonné"

    def get_authors(self):
        orgs: list[Organisation] = adapt(g.user).get_followees(cls=Organisation)
        journalists = set()
        for org in orgs:
            if org.type == OrganisationTypeEnum.MEDIA:
                journalists.update(list(org.members))
        return journalists


class JournalistsTab(Tab):
    id = "journalists"
    label = "Journalistes"
    tip = "Les journalistes que je suis"

    def get_authors(self):
        return adapt(g.user).get_followees()


class ComTab(Tab):
    id = "com"
    label = "Idées & Comm"
    tip = "Communiqués de presse"

    def get_posts(self, filter_bar):
        return []
        # sort_order = filter_bar.sort_order
        #
        # match sort_order:
        #     # TODO
        #     # case "likes":
        #     #     order = PressRelease.like_count.desc()
        #     # case "comments":
        #     #     order = PressRelease.comment_count.desc()
        #     case _:
        #         # TODO
        #         order = PressRelease.created_at.desc()
        #
        # stmt = (
        #     sa.select(PressRelease)
        #     .where(PressRelease.status == PublicationStatus.PUBLIC)
        #     .order_by(order)
        #     .options(selectinload(PressRelease.owner))
        #     .limit(30)
        # )
        # return get_multi(PressRelease, stmt)
