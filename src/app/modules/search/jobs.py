"""Dramatiq jobs that keep the search index in sync.

A receiver in ``search/receivers.py`` enqueues ``reindex_from_source``
with the *source* object's type and id (e.g. the wip ``Article`` that
triggered the domain signal, not the public ``ArticlePost`` mirror).
The job runs in a Dramatiq worker after the request transaction has
committed, looks up the corresponding indexable Post, then either
upserts it (if currently public) or deletes its index entry.

Decoupling the signal payload from the indexable model avoids order-
of-receiver issues: the wire/event mirror receiver and our enqueuing
receiver both subscribe to the same signal; by the time the job runs,
the mirror is on disk and visible to a fresh session.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import svcs.flask
from loguru import logger
from sqlalchemy import select

from app.dramatiq.job import job
from app.flask.extensions import db

from .adapters import doc_id, is_public, to_doc
from .engine import SearchEngine
from .registry import lookup_by_source_type

if TYPE_CHECKING:
    from app.models.content.base import BaseContent


@job()
def reindex_from_source(source_type: str, source_id: int) -> None:
    """Sync the index for the post identified by ``(source_type, source_id)``.

    For wire/event the source is the wip entity and we resolve to its
    public mirror Post via the registry's ``fk_column``. For
    marketplace/group/user/organisation the source IS the indexable
    object; the lookup is a plain primary-key fetch.
    """
    try:
        entry = lookup_by_source_type(source_type)
    except KeyError as exc:
        raise ValueError(str(exc)) from exc

    post = _find_post(entry, source_id)
    if post is None:
        # Either the mirror hasn't been written yet (signal race —
        # retry covers it) or there's nothing to index. Either way,
        # nothing to do right now.
        logger.debug(
            "search: no post for ({}, {}); skipping", source_type, source_id
        )
        return

    engine = svcs.flask.container.get(SearchEngine)
    _apply(engine, post)


def _find_post(entry, source_id: int) -> BaseContent | None:
    if entry.fk_column is None:
        return db.session.get(entry.model, source_id)
    stmt = select(entry.model).where(
        getattr(entry.model, entry.fk_column) == source_id
    )
    return db.session.scalar(stmt)


def _apply(engine: SearchEngine, post: BaseContent) -> None:
    """Upsert ``post`` if it is currently public, otherwise delete its
    index entry. ``doc_id`` skips the URL/tags work that ``to_doc``
    does, so the delete path stays cheap.
    """
    if is_public(post):
        engine.upsert(to_doc(post))
    else:
        engine.delete(doc_id(post))
