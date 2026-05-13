# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Admin dashboard for the Dramatiq queue.

Read-only view backed by the `dramatiq.queue` table that
dramatiq-pg manages in the application database. No Redis or
RabbitMQ involved — the data lives next to the rest of the app, so
we can read it via the same SQLAlchemy session.

Three sections are exposed:

1. Per-queue counts by state (queued / consumed / rejected / done)
2. List of registered actors (from the live broker), grouped by
   their target queue.
3. Most recent messages (latest mtime first) with their state and
   a peek of the JSONB payload so an operator can spot stuck or
   loop-retrying jobs at a glance.

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

_RECENT_LIMIT = 25


@blueprint.route("/dramatiq")
@nav(parent="index", icon="briefcase", label="Dramatiq")
def dramatiq_dashboard():
    """Render the Dramatiq monitoring page."""
    return render_template(
        "admin/pages/dramatiq.j2",
        title="Dramatiq",
        schema_present=_schema_present(),
        queues=_queue_state_counts(),
        actors=_registered_actors(),
        recent=_recent_messages(),
        recent_limit=_RECENT_LIMIT,
    )


def _schema_present() -> bool:
    """True iff the `dramatiq.queue` table exists in this database.

    Falls back to a dialect-aware probe so SQLite (used in tests
    with the StubBroker) returns False cleanly instead of erroring
    on the missing `information_schema` view.
    """
    bind = db.session.get_bind()
    if bind.dialect.name != "postgresql":
        # dramatiq-pg is Postgres-only; under SQLite/other test
        # backends the schema is by definition absent.
        return False
    row = db.session.execute(
        text(
            "SELECT 1 FROM information_schema.tables "
            "WHERE table_schema = 'dramatiq' AND table_name = 'queue'"
        )
    ).first()
    return row is not None


def _queue_state_counts() -> list[dict[str, Any]]:
    """One row per (queue_name, state), with count + last-update time.

    Sorted by queue name, then by state in our preferred display
    order (queued first, done last) so the most actionable state
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
                     CASE state
                       WHEN 'queued'   THEN 0
                       WHEN 'consumed' THEN 1
                       WHEN 'rejected' THEN 2
                       WHEN 'done'     THEN 3
                       ELSE 4
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


def _recent_messages() -> list[dict[str, Any]]:
    """Latest `_RECENT_LIMIT` rows from the queue table.

    We include a short summary of the JSONB `message` payload so the
    operator can spot patterns at a glance — actor name + a few key
    args.
    """
    if not _schema_present():
        return []

    rows = db.session.execute(
        text(
            """
            SELECT message_id,
                   queue_name,
                   state,
                   mtime,
                   message
            FROM dramatiq.queue
            ORDER BY mtime DESC
            LIMIT :limit
            """
        ),
        {"limit": _RECENT_LIMIT},
    ).all()

    out: list[dict[str, Any]] = []
    for r in rows:
        msg = r.message or {}
        out.append(
            {
                "message_id": str(r.message_id),
                "queue": r.queue_name,
                "state": r.state,
                "mtime": r.mtime,
                "actor_name": msg.get("actor_name", "?"),
                "args_preview": _preview_args(msg.get("args", [])),
            }
        )
    return out


def _preview_args(args: list[Any]) -> str:
    """Render `args` as a short, single-line preview for the table.

    Long values are truncated to keep the row compact; we don't
    want to leak full secrets into the admin UI if someone enqueued
    a token by accident.
    """
    if not args:
        return ""
    parts: list[str] = []
    for a in args[:3]:
        s = repr(a)
        if len(s) > 40:
            s = s[:37] + "…"
        parts.append(s)
    if len(args) > 3:
        parts.append(f"+{len(args) - 3} more")
    return ", ".join(parts)
