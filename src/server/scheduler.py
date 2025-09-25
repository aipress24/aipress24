"""Background scheduler for periodic tasks."""

# Copyright (c) 2024, Abilian SAS & TCA
from __future__ import annotations

import time

import schedule

from app.flask.main import create_app
from app.modules.search.backend import SearchBackend


def index() -> None:
    """Perform search index update task."""
    print("Indexing...")
    app = create_app()
    with app.app_context():
        backend = SearchBackend()
        backend.index_all()


def scheduler() -> None:
    """Run the background task scheduler.

    Schedules periodic tasks like search indexing.
    """
    print("Starting scheduler")
    schedule.every().hour.do(index)

    while True:
        print("Scheduling")
        schedule.run_pending()
        time.sleep(60)
