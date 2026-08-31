# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

import abc
from collections.abc import Iterable
from operator import itemgetter
from typing import ClassVar

import arrow
import sqlalchemy as sa
from flask import g, session
from pipe import groupby
from sqlalchemy.orm import selectin_polymorphic, selectinload

from app.enums import MEDIA_BW_TYPES
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

from ._filters import (
    CONTENT_KIND_ARTICLES,
    CONTENT_KIND_EVENTS,
    FilterBar,
)

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

#: Combien d'événements le fil accepte, **en plus** des publications.
#:
#: Ticket #0324 : sans plafond, la fusion gardait les trente contenus
#: les plus récents de l'union — et si les événements étaient plus
#: récents, ils prenaient les trente places. Le portail NEWS n'affichait
#: plus un seul article. `WIR-05` l'avait prévu — « l'événement pouvant
#: sinon noyer l'actualité chaude » — mais le filtre de type de contenu
#: montre tout par défaut, donc la noyade précédait le remède.
#:
#: Un budget **supplémentaire** et non une part du budget : aucune
#: publication qui figurait dans le fil n'en disparaît parce qu'un
#: événement est arrivé. Le Wall reste un fil d'actualité que des
#: événements accompagnent.
WALL_EVENTS_LIMIT = 5


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
            case "shares":
                order = Post.share_count.desc()
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
                # Bug 0268: each card renders its cover image's media URL.
                # The two post types read from two different image tables,
                # hence one loader each.
                selectinload(ArticlePost.cover_image),
                selectinload(PressReleasePost.cover_image),
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
    """Le fil personnalisé — le seul onglet qui mêle plusieurs natures
    de contenu (WIR-01).

    Les quatre autres onglets qualifient des **sources de presse** :
    agences, médias, journalistes, communicants. Un événement
    n'appartient à aucune, et c'est pourquoi il n'entre que dans
    celui-ci.
    """

    id = "wall"
    label = "All"
    tip = "Fil d'actus"
    post_type_allow: ClassVar[set[str]] = {"article", "post"}

    def get_authors(self):
        return []

    def get_posts(self, filter_bar: FilterBar) -> list:
        """Les publications du fil, événements compris (WIR-01, W1).

        Une seconde requête fusionnée, et non un héritage de `Post` :
        `EventPost` descend de `BaseContent` par une autre branche, et
        l'aligner ferait porter à une table peuplée le coût d'un simple
        affichage (arbitrage `M2`, option W1).

        **Uniquement dans l'ordre chronologique.** Les autres tris
        classent des articles — ventes, consultations payantes — et
        n'ont pas d'équivalent sur un événement ; les y mêler
        ordonnerait deux listes selon deux critères différents. Sous ces
        tris, le fil reste ce qu'il était.
        """
        kinds = _selected_content_kinds(filter_bar)

        # Chaque nature écartée est une requête qu'on n'émet pas, plutôt
        # qu'un résultat qu'on jette.
        posts = super().get_posts(filter_bar) if CONTENT_KIND_ARTICLES in kinds else []
        if CONTENT_KIND_EVENTS not in kinds or filter_bar.sort_order != "date":
            return posts

        return _merge_by_date([*posts, *_wall_events(filter_bar)])


def _selected_content_kinds(filter_bar: FilterBar) -> set[str]:
    """Les natures de contenu retenues par le filtre (WIR-05).

    Aucune sélection vaut « toutes » : c'est le comportement de tous les
    autres filtres de cette barre, et un fil vide par défaut serait une
    surprise désagréable.
    """
    chosen = {
        f["value"] for f in filter_bar.active_filters if f["id"] == "content_kind"
    }
    return chosen or {CONTENT_KIND_ARTICLES, CONTENT_KIND_EVENTS}


def _merge_by_date(items: list) -> list:
    """Fusionner deux natures de contenu, du plus récent au plus ancien.

    **Sans troncature** : chaque source arrive déjà plafonnée, et
    rogner ici reviendrait à laisser la nature la plus récente évincer
    l'autre — c'est ce qui a vidé le portail NEWS de ses articles
    (#0324).

    Les publications **sans date** sont mises de côté et remises en
    queue, plutôt que ramenées à une date d'origine qui les trierait
    par accident. Un contenu public sans date de publication est une
    anomalie de données ; elle ne doit ni vider le fil de tout le monde,
    ni se déguiser en 1970.
    """
    dated = [item for item in items if item.published_at]
    undated = [item for item in items if not item.published_at]
    dated.sort(key=lambda item: item.published_at, reverse=True)
    return [*dated, *undated]


def _wall_events(filter_bar: FilterBar) -> list:
    """Les événements éligibles au fil (WIR-03).

    Publics, non annulés, à venir. Les deux autres critères que la règle
    énonce — « son organisateur ou son éditeur fait partie des
    organisations suivies », « son secteur figure parmi les secteurs
    suivis » — décrivent une personnalisation que **le Wall n'a pour
    aucun contenu** : il liste toutes les publications publiques,
    `get_authors()` y rend une liste vide, et rien dans le dépôt ne
    permet de suivre un secteur. Les appliquer aux seuls événements les
    rendrait moins visibles que les articles, ce qui est l'inverse de
    l'intention.
    """
    from app.modules.events.models import EventPost

    now = arrow.utcnow()
    stmt = (
        sa.select(EventPost)
        .where(EventPost.status == PublicationStatus.PUBLIC)
        .where(EventPost.cancelled_at.is_(None))
        .where(EventPost.start_datetime >= now)
        .order_by(EventPost.published_at.desc())
        .options(
            selectinload(EventPost.owner).options(
                selectinload(User.organisation),
                selectinload(User.profile),
                selectinload(User.roles),
            ),
            selectinload(EventPost.publisher),
        )
        .limit(WALL_EVENTS_LIMIT)
    )

    for filter_id, filter_values in filter_bar.active_filters | groupby(
        itemgetter("id")
    ):
        if filter_id not in ALLOWED_FILTER_FIELDS:
            continue
        values = {f["value"] for f in filter_values}
        stmt = stmt.where(getattr(EventPost, filter_id).in_(values))

    return list(db.session.scalars(stmt))


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
            if org.bw_active in MEDIA_BW_TYPES and org.id not in agency_ids
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
