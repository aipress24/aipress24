# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Admin dashboard for the Dramatiq queue.

Read-only view backed by the `dramatiq` schema that
dramatiq-postgres manages in the application database. No Redis or
RabbitMQ involved — the data lives next to the rest of the app, so
we can read it via the same SQLAlchemy session.

Three sections are exposed:

1. Active workers reporting heartbeats in `dramatiq.worker`.
2. Per-queue counts by state (queued / consumed / rejected) in `dramatiq.queue`.
3. List of registered actors (from the live broker), grouped by
   their target queue.

The page is read-only on purpose. Mutating actions (requeue, purge,
flush) deserve confirm-dialogs + audit logging and are out of scope
for this minimal dashboard — file a follow-up if the team wants
them.
"""

from __future__ import annotations

from typing import Any

import dramatiq
from flask import render_template
from sqlalchemy import text

from app.flask.extensions import db
from app.flask.lib.nav import nav
from app.modules.admin import blueprint


@blueprint.route("/dramatiq")
@nav(parent="index", icon="briefcase", label="Dramatiq")
def dramatiq_dashboard():
    """Render the Dramatiq monitoring page."""
    return render_template(
        "admin/pages/dramatiq.j2",
        title="Dramatiq",
        schema_present=_schema_present(),
        workers=_active_workers(),
        queues=_queue_state_counts(),
        actors=_registered_actors(),
    )


def _schema_present() -> bool:
    """True iff the `dramatiq.queue` table exists in this database.

    Falls back to a dialect-aware probe so SQLite (used in tests
    with the StubBroker) returns False cleanly instead of erroring
    on the missing `information_schema` view.
    """
    bind = db.session.get_bind()
    if bind.dialect.name != "postgresql":
        # dramatiq-postgres is Postgres-only; under SQLite/other test
        # backends the schema is by definition absent.
        return False
    row = db.session.execute(
        text(
            "SELECT 1 FROM information_schema.tables "
            "WHERE table_schema = 'dramatiq' AND table_name = 'queue'"
        )
    ).first()
    return row is not None


def _active_workers() -> list[dict[str, Any]]:
    """List worker processes reporting heartbeats in `dramatiq.worker`."""
    if not _schema_present():
        return []

    rows = db.session.execute(
        text(
            """
            SELECT worker_id,
                   heartbeat_at,
                   EXTRACT(EPOCH FROM (NOW() - heartbeat_at)) AS age_seconds
            FROM dramatiq.worker
            ORDER BY heartbeat_at DESC
            """
        )
    ).all()

    out: list[dict[str, Any]] = []
    for r in rows:
        age = r.age_seconds if r.age_seconds is not None else 999999
        is_active = age <= 30
        if age < 60:
            age_str = f"{int(age)}s ago"
        elif age < 3600:
            age_str = f"{int(age // 60)}m ago"
        else:
            age_str = f"{int(age // 3600)}h ago"

        out.append(
            {
                "worker_id": str(r.worker_id),
                "heartbeat_at": r.heartbeat_at,
                "age": age_str,
                "is_active": is_active,
            }
        )
    return out


def _queue_state_counts() -> list[dict[str, Any]]:
    """One row per (queue_name, state), with count + last-update time.

    Sorted by queue name, then by state in our preferred display
    order (queued first, rejected last) so the most actionable state
    appears at the top of each group.
    """
    if not _schema_present():
        return []

    rows = db.session.execute(
        text(
            """
            SELECT queue_name,
                   state,
                   COUNT(*) AS n,
                   MAX(mtime) AS last_mtime
            FROM dramatiq.queue
            GROUP BY queue_name, state
            ORDER BY queue_name,
                     CASE state::text
                       WHEN 'queued'   THEN 0
                       WHEN 'consumed' THEN 1
                       WHEN 'rejected' THEN 2
                       ELSE 3
                     END
            """
        )
    ).all()
    return [
        {
            "queue": r.queue_name,
            "state": r.state,
            "count": r.n,
            "last_mtime": r.last_mtime,
        }
        for r in rows
    ]


def _registered_actors() -> list[dict[str, Any]]:
    """List the actors currently registered on the live broker.

    `dramatiq.get_broker().actors` is a dict of name -> Actor. We
    expose just the fields useful for the operator: actor name,
    target queue, priority, and the configured retry options.
    """
    broker = dramatiq.get_broker()
    actors_dict = getattr(broker, "actors", {})
    out: list[dict[str, Any]] = []
    for name, actor in actors_dict.items():
        out.append(
            {
                "name": name,
                "queue": getattr(actor, "queue_name", "default"),
                "priority": getattr(actor, "priority", 0),
                "options": getattr(actor, "options", {}),
            }
        )
    out.sort(key=lambda a: (a["queue"], a["name"]))
    return out
