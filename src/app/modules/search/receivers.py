"""Domain-signal receivers that keep the search index up to date.

We piggyback on the existing publish/unpublish/update signals for
articles, press releases, and events. Each receiver enqueues a Dramatiq
job that, after the request transaction commits, reads the mirror Post
from a fresh session and syncs its state to the index.

The receivers are intentionally trivial — all the indexing logic lives
in ``jobs.reindex_from_source``. Splitting publish/unpublish/update is
kept for clarity (each signal has obvious semantics) even though the
three paths feed the same job.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.signals import (
    article_published,
    article_unpublished,
    article_updated,
    communique_published,
    communique_unpublished,
    communique_updated,
    event_published,
    event_unpublished,
    event_updated,
    group_published,
    group_unpublished,
    marketplace_published,
    marketplace_unpublished,
    org_activated,
    org_deactivated,
    user_activated,
    user_deactivated,
)

from .jobs import reindex_from_source

if TYPE_CHECKING:
    from app.models.auth import User
    from app.models.organisation import Organisation
    from app.modules.biz.models import MarketplaceContent
    from app.modules.swork.models import Group
    from app.modules.wip.models import Article, Communique
    from app.modules.wip.models.eventroom import Event


# ── Article ────────────────────────────────────────────────────────


@article_published.connect
def _on_article_published(article: Article) -> None:
    reindex_from_source.send("article", article.id)


@article_unpublished.connect
def _on_article_unpublished(article: Article) -> None:
    reindex_from_source.send("article", article.id)


@article_updated.connect
def _on_article_updated(article: Article) -> None:
    reindex_from_source.send("article", article.id)


# ── Press release (communiqué) ─────────────────────────────────────


@communique_published.connect
def _on_communique_published(communique: Communique) -> None:
    reindex_from_source.send("press_release", communique.id)


@communique_unpublished.connect
def _on_communique_unpublished(communique: Communique) -> None:
    reindex_from_source.send("press_release", communique.id)


@communique_updated.connect
def _on_communique_updated(communique: Communique) -> None:
    reindex_from_source.send("press_release", communique.id)


# ── Event ──────────────────────────────────────────────────────────


@event_published.connect
def _on_event_published(event: Event) -> None:
    reindex_from_source.send("event", event.id)


@event_unpublished.connect
def _on_event_unpublished(event: Event) -> None:
    reindex_from_source.send("event", event.id)


@event_updated.connect
def _on_event_updated(event: Event) -> None:
    reindex_from_source.send("event", event.id)


# ── Marketplace (mission / project / job / editorial product) ──────


@marketplace_published.connect
def _on_marketplace_published(offer: MarketplaceContent) -> None:
    reindex_from_source.send("marketplace", offer.id)


@marketplace_unpublished.connect
def _on_marketplace_unpublished(offer: MarketplaceContent) -> None:
    reindex_from_source.send("marketplace", offer.id)


# ── Group ──────────────────────────────────────────────────────────


@group_published.connect
def _on_group_published(group: Group) -> None:
    reindex_from_source.send("group", group.id)


@group_unpublished.connect
def _on_group_unpublished(group: Group) -> None:
    reindex_from_source.send("group", group.id)


# ── User (members directory) ───────────────────────────────────────


@user_activated.connect
def _on_user_activated(user: User) -> None:
    reindex_from_source.send("user", user.id)


@user_deactivated.connect
def _on_user_deactivated(user: User) -> None:
    reindex_from_source.send("user", user.id)


# ── Organisation ───────────────────────────────────────────────────


@org_activated.connect
def _on_org_activated(org: Organisation) -> None:
    reindex_from_source.send("organisation", org.id)


@org_deactivated.connect
def _on_org_deactivated(org: Organisation) -> None:
    reindex_from_source.send("organisation", org.id)
