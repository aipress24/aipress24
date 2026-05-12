"""Cron actor: catch-up search-index rebuild.

Live indexing happens via domain signals (see
``app.modules.search.receivers``). This hourly job is a safety net —
it re-walks the database and rebuilds the index from scratch in case
a signal was dropped (worker crash, transient broker error, race
between request commit and worker pickup).

Runs at HH:15 to avoid colliding with the reputation actor at HH:00.
"""

from __future__ import annotations

import time

from loguru import logger

from app.dramatiq.scheduler import crontab
from app.modules.search.cli import rebuild_index


@crontab("15 * * * *")
def rebuild_search_index() -> None:
    logger.info("cron: search rebuild starting")
    started = time.monotonic()
    counts = rebuild_index(show_progress=False)
    elapsed = time.monotonic() - started
    total = sum(counts.values())
    logger.info(
        "cron: search rebuild done in {:.1f}s — {} docs ({})",
        elapsed,
        total,
        counts,
    )
