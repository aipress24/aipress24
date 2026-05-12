"""Background scheduler for periodic tasks."""

# Copyright (c) 2024, Abilian SAS & TCA
from __future__ import annotations

import time

import schedule
from loguru import logger

from app.flask.main import create_app
from app.modules.search.cli import rebuild_index


def index() -> None:
    """Catch-up reindex of the wesh search engine.

    Live indexing happens via domain signals in
    ``app.modules.search.receivers``. This hourly job is a safety
    net: it re-walks the database and rebuilds the index from
    scratch, in case a signal was dropped (worker crash, Redis blip).
    """
    logger.info("scheduler: rebuilding search index")
    app = create_app()
    with app.app_context():
        counts = rebuild_index()
    logger.info("scheduler: search index rebuild done — {}", counts)


def scheduler() -> None:
    """Run the background task scheduler.

    Schedules periodic tasks like search indexing.
    """
    logger.info("Starting scheduler")
    schedule.every().hour.do(index)

    while True:
        schedule.run_pending()
        time.sleep(60)
