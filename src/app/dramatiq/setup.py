"""Dramatiq broker setup and initialization."""
# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from urllib.parse import urlparse, urlunparse

import dramatiq
from dramatiq.brokers.stub import StubBroker
from dramatiq_pg import PostgresBroker, generate_init_sql
from loguru import logger

from app.flask.main import create_app

from .job import register_regular_jobs
from .middleware import AppContextMiddleware
from .scheduler import register_cron_jobs


def init_dramatiq(app) -> None:
    """Initialize Dramatiq with a Postgres broker and Flask app context.

    The queue lives in the same database as the app (under the
    ``dramatiq`` schema, managed by ``dramatiq-pg``). No Redis needed.

    Under ``TESTING`` we wire a ``StubBroker`` instead — messages stay
    in memory and tests don't need a worker. Tests that need to assert
    on enqueued work can introspect the StubBroker directly.

    Args:
        app: Flask application instance.
    """
    logger.info("Setting up Dramatiq")

    if app.config.get("TESTING"):
        broker = StubBroker()
        dramatiq.set_broker(broker)
        register_cron_jobs()
        register_regular_jobs()
        return

    db_url = _normalise_pg_url(app.config["SQLALCHEMY_DATABASE_URI"])
    broker = PostgresBroker(url=db_url, results=False)
    broker.add_middleware(AppContextMiddleware(app))
    dramatiq.set_broker(broker)

    _ensure_dramatiq_schema(broker)

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


def _normalise_pg_url(url: str) -> str:
    """Strip SQLAlchemy driver suffixes (``postgresql+psycopg2://``)
    that psycopg2 doesn't understand. Pass anything else through.
    """
    parts = urlparse(url)
    if "+" in parts.scheme:
        clean_scheme = parts.scheme.split("+", 1)[0]
        return urlunparse(parts._replace(scheme=clean_scheme))
    return url


_BOOTSTRAP_LOCK_ID = 0xDEAD_DD11_BB55  # arbitrary 64-bit constant


def _ensure_dramatiq_schema(broker: PostgresBroker) -> None:
    """Run dramatiq-pg's init SQL once if the schema isn't there yet.

    The generated DDL is not idempotent (``CREATE TYPE`` has no
    ``IF NOT EXISTS`` clause, and ``CREATE SCHEMA IF NOT EXISTS``
    races against the underlying ``pg_namespace`` insert when several
    processes call it concurrently — e.g. honcho starting ``vite`` and
    ``backend`` in parallel during dev), so we serialize with a
    Postgres advisory lock and check existence under the lock. The
    lock is transaction-scoped: ``pg_advisory_xact_lock`` releases
    automatically on commit.

    In production, the app's DB user typically does not have DDL
    privileges on the database — the schema is provisioned once at
    install time by an admin (see runbook below). We catch the
    permission error and log a clear pointer rather than crashing
    every command that boots the app:

        psql -d <DB> -c "$(python -c 'from dramatiq_pg import generate_init_sql; print(generate_init_sql())')"
    """
    import psycopg2.errors

    conn = broker.pool.getconn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT pg_advisory_xact_lock(%s)", (_BOOTSTRAP_LOCK_ID,))
            cur.execute(
                """
                SELECT 1
                FROM information_schema.tables
                WHERE table_schema = 'dramatiq' AND table_name = 'queue'
                """
            )
            if cur.fetchone():
                logger.debug("dramatiq schema already present")
                conn.commit()
                return
            logger.info("Creating dramatiq schema")
            try:
                cur.execute(generate_init_sql())
                conn.commit()
            except psycopg2.errors.InsufficientPrivilege:
                conn.rollback()
                logger.error(
                    "dramatiq schema is missing and the current DB user "
                    "lacks DDL privileges to create it. Provision it once "
                    "by running, as a DB admin:\n"
                    '  psql -d <DB> -c "$(python -c '
                    "'from dramatiq_pg import generate_init_sql; "
                    "print(generate_init_sql())')\"\n"
                    "Until then, jobs sent via .send() will fail at "
                    "enqueue time."
                )
    finally:
        broker.pool.putconn(conn)
