# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

import abc
from collections.abc import Iterable
from operator import itemgetter
from typing import ClassVar

import sqlalchemy as sa
from flask import g, session
from pipe import groupby
from sqlalchemy.orm import selectin_polymorphic, selectinload

from app.flask.extensions import db
from app.flask.sqla import get_multi
from app.models.auth import User
from app.models.lifecycle import PublicationStatus
from app.models.organisation import Organisation
from app.modules.bw.bw_activation.user_utils import (
    filter_agency_org_ids,
)
from app.modules.wire.models import (
    ArticlePost,
    ArticlePurchase,
    Post,
    PressReleasePost,
    PurchaseStatus,
)
from app.services.social_graph import adapt

from ._filters import FilterBar

# Allowed filter fields for ORM queries - prevents arbitrary attribute access
ALLOWED_FILTER_FIELDS = {
    "sector",
    "topic",
    "genre",
    "section",
    "pays_zip_ville",
    "departement",
    "ville",
}

DEFAULT_POSTS_LIMIT = 30


def _members_of_orgs(org_ids: set[int]) -> set[User]:
    """All members of the given orgs in one query — batches what was a
    per-org `org.members` lazy-load in the Agences / Médias tabs."""
    if not org_ids:
        return set()
    return set(
        db.session.scalars(sa.select(User).where(User.organisation_id.in_(org_ids)))
    )


def get_tabs() -> list[Tab]:
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
    post_type_allow: ClassVar[set[str]]

    @property
    def is_active(self) -> bool:
        return session["wire:tab"] == self.id

    def get_posts(self, filter_bar: FilterBar) -> list[Post]:
        stmt = self.get_stmt(filter_bar)

        authors = self.get_authors()
        # Only filter by author if there are specific authors to filter by
        # Empty list means "no filter", not "match no one"
        if authors:
            author_ids = [f.id for f in authors]
            stmt = stmt.where(Post.owner_id.in_(author_ids))

        posts = get_multi(Post, stmt)
        return posts

    def get_authors(self) -> Iterable[User]:
        """Override in subclasses to filter by certain authors."""
        return []

    def get_stmt(self, filter_bar: FilterBar) -> sa.Select:
        active_filters = filter_bar.active_filters
        sort_order = filter_bar.sort_order

        # Ticket #0193 — « Popularité (vues) » and « Ventes » in the
        # Trier menu both feed off PAID article purchases now, not the
        # raw `Post.view_count`. Each is a scalar subquery so the wall
        # query stays a single SELECT.
        match sort_order:
            case "views":
                # Reuse the same expression as
                # `get_paid_consultations_count` (direct + gift
                # beneficiaries). Otherwise the wall sort orders by a
                # number different from the eye-icon counter displayed
                # on the card — same article shows « 25 vues » but
                # sits below an article showing « 10 vues ».
                from app.modules.wire.services.purchase_aggregates import (
                    paid_consultation_count_subquery,
                )

                order = paid_consultation_count_subquery(Post.id).desc()
            case "sales":
                sales_amount = (
                    sa.select(
                        sa.func.coalesce(sa.func.sum(ArticlePurchase.amount_cents), 0)
                    )
                    .select_from(ArticlePurchase)
                    .where(ArticlePurchase.post_id == Post.id)
                    .where(ArticlePurchase.status == PurchaseStatus.PAID)
                    .correlate(Post)
                    .scalar_subquery()
                )
                order = sales_amount.desc()
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
            .options(
                # Each card reads the author's org (name), profile (job
                # title) and roles (community colour via profile_image) —
                # all SELECT-per-card N+1s. Batch them with the author.
                selectinload(Post.owner).options(
                    selectinload(User.organisation),
                    selectinload(User.profile),
                    selectinload(User.roles),
                ),
                # The card also shows the publisher org ("Publié par …") —
                # another SELECT-per-card relationship.
                selectinload(Post.publisher),
                # Batch-load the subclass columns (newsroom_id, publisher_type,
                # …). The wall queries the base `Post`, but the cards are
                # ArticlePost/PressReleasePost; accessing their subclass
                # columns was a SELECT-per-card refresh (single-table poly).
                selectin_polymorphic(Post, [ArticlePost, PressReleasePost]),
            )
            .limit(DEFAULT_POSTS_LIMIT)
        )

        if self.post_type_allow:
            stmt = stmt.where(Post.type.in_(self.post_type_allow))

        for filter_id, filter_values in active_filters | groupby(itemgetter("id")):
            if filter_id == "tag":
                continue
            # Use explicit allowlist instead of hasattr for security
            if filter_id not in ALLOWED_FILTER_FIELDS:
                continue
            values = {f["value"] for f in filter_values}
            where_clause = getattr(Post, filter_id).in_(values)
            stmt = stmt.where(where_clause)

        return stmt


class WallTab(Tab):
    id = "wall"
    label = "All"
    tip = "Fil d'actus"
    post_type_allow: ClassVar[set[str]] = {"article", "post"}

    def get_authors(self):
        return []


class AgenciesTab(Tab):
    id = "agencies"
    label = "Agences"
    tip = "Agences de Presse"
    post_type_allow: ClassVar[set[str]] = {"article", "post"}

    def get_authors(self):
        orgs: list[Organisation] = adapt(g.user).get_followees(cls=Organisation)
        agency_ids = filter_agency_org_ids(orgs)
        return _members_of_orgs(agency_ids)


class MediasTab(Tab):
    id = "media"
    label = "Médias"
    tip = "Médias (presse, en ligne...) auxquels je suis abonné"
    post_type_allow: ClassVar[set[str]] = {"article", "post"}

    def get_authors(self):
        orgs: list[Organisation] = adapt(g.user).get_followees(cls=Organisation)
        agency_ids = filter_agency_org_ids(orgs)
        media_ids = {
            org.id
            for org in orgs
            if org.bw_active == "media" and org.id not in agency_ids
        }
        return _members_of_orgs(media_ids)


class JournalistsTab(Tab):
    id = "journalists"
    label = "Journalistes"
    tip = "Les journalistes que je suis"
    post_type_allow: ClassVar[set[str]] = {"article", "post"}

    def get_authors(self):
        return adapt(g.user).get_followees()


class ComTab(Tab):
    """Tab for press releases (communiqués de presse)."""

    id = "com"
    label = "Idées & Comm"
    tip = "Communiqués de presse"
    post_type_allow: ClassVar[set[str]] = {"press_release"}
