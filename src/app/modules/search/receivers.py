"""Domain-signal receivers that keep the search index up to date.

We piggyback on the existing publish/unpublish/update signals for
articles, press releases, and events. Each receiver enqueues a Dramatiq
job that, after the request transaction commits, reads the mirror Post
from a fresh session and syncs its state to the index.

The receivers are intentionally trivial — all the indexing logic lives
in ``jobs.reindex_from_source``. Publish, unpublish and update stay
separate *signals* because each has obvious semantics, but they feed one
receiver per source type: the three bodies were identical, and stacking
the ``connect`` decorators says so outright (audit 2026-09-02).
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
    from app.modules.wip.models import Article, Communique
    from app.modules.wip.models.eventroom import Event


@article_published.connect
@article_unpublished.connect
@article_updated.connect
def _reindex_article(article: Article) -> None:
    reindex_from_source.send("article", article.id)


@communique_published.connect
@communique_unpublished.connect
@communique_updated.connect
def _reindex_press_release(communique: Communique) -> None:
    reindex_from_source.send("press_release", communique.id)


@event_published.connect
@event_unpublished.connect
@event_updated.connect
def _reindex_event(event: Event) -> None:
    reindex_from_source.send("event", event.id)


@marketplace_published.connect
@marketplace_unpublished.connect
def _reindex_marketplace(offer: MarketplaceContent) -> None:
    reindex_from_source.send("marketplace", offer.id)


@user_activated.connect
@user_deactivated.connect
def _reindex_user(user: User) -> None:
    reindex_from_source.send("user", user.id)


@org_activated.connect
@org_deactivated.connect
def _reindex_organisation(org: Organisation) -> None:
    reindex_from_source.send("organisation", org.id)
