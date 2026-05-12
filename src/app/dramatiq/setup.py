"""Dramatiq broker setup and initialization."""
# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

import dramatiq
from dramatiq.brokers.redis import RedisBroker
from dramatiq.brokers.stub import StubBroker
from loguru import logger

from app.flask.main import create_app

from .job import register_regular_jobs
from .middleware import AppContextMiddleware
from .scheduler import register_cron_jobs

DEFAULT_REDIS_URL = "redis://localhost:6379/0"


def init_dramatiq(app) -> None:
    """Initialize Dramatiq with Redis broker and Flask app context.

    Under ``TESTING`` we wire a ``StubBroker`` instead — keeps the test
    suite from needing a live Redis just because some signal happens
    to enqueue an indexing job. Messages accumulate in memory and are
    discarded at process exit; tests that need to assert on enqueued
    work can introspect the StubBroker directly.

    Args:
        app: Flask application instance.
    """
    logger.info("Setting up Dramatiq")

    if app.config.get("TESTING"):
        broker = StubBroker()
    else:
        redis_url = app.config.get("DRAMATIC_REDIS_URL")
        if not redis_url:
            redis_url = app.config.get("REDIS_URL")
        if not redis_url:
            redis_url = DEFAULT_REDIS_URL
        middleware = [AppContextMiddleware(app)]
        broker = RedisBroker(url=redis_url, middleware=middleware)
    dramatiq.set_broker(broker)

    register_cron_jobs()
    register_regular_jobs()


def setup_broker():
    """Setup and return a configured Dramatiq broker.

    Returns:
        Dramatiq broker instance.
    """
    app = create_app()
    init_dramatiq(app)
    return dramatiq.get_broker()
