# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""N+1 Query Detection Middleware.

Detects potential N+1 query issues by tracking SQL queries during requests
and identifying patterns where similar queries are executed multiple times.

Usage:
    from app.flask.lib.n_plus_one_detector import init_n_plus_one_detector

    def create_app():
        app = Flask(__name__)
        init_n_plus_one_detector(app)
        return app

Configuration (in app.config):
    N_PLUS_ONE_ENABLED: bool | None = None  # None = use debug mode, True/False = explicit
    N_PLUS_ONE_THRESHOLD: int = 3  # Min repeated queries to trigger warning
    N_PLUS_ONE_LOG_LEVEL: str = "WARNING"  # Log level for alerts
    N_PLUS_ONE_RAISE: bool = False  # Raise exception instead of logging

The detector is active when:
    - N_PLUS_ONE_ENABLED is explicitly True, OR
    - N_PLUS_ONE_ENABLED is None (default) AND app.debug is True
"""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from flask import g, has_request_context
from loguru import logger
from sqlalchemy import event
from sqlalchemy.engine import Engine

if TYPE_CHECKING:
    from flask import Flask


@dataclass
class QueryInfo:
    """Information about a tracked query."""

    statement: str
    parameters: tuple | dict | None
    normalized: str
    count: int = 1
    locations: list[str] = field(default_factory=list)


@dataclass
class QueryTracker:
    """Tracks queries during a request."""

    queries: list[QueryInfo] = field(default_factory=list)
    patterns: dict[str, list[QueryInfo]] = field(
        default_factory=lambda: defaultdict(list)
    )
    enabled: bool = True

    def add_query(self, statement: str, parameters: tuple | dict | None) -> None:
        """Record a query execution."""
        if not self.enabled:
            return

        normalized = normalize_query(statement)
        info = QueryInfo(
            statement=statement,
            parameters=parameters,
            normalized=normalized,
        )
        self.queries.append(info)
        self.patterns[normalized].append(info)

    def get_n_plus_one_candidates(self, threshold: int = 3) -> list[tuple[str, int]]:
        """Return query patterns that appear more than threshold times."""
        candidates = []
        for pattern, queries in self.patterns.items():
            if len(queries) >= threshold:
                candidates.append((pattern, len(queries)))
        return sorted(candidates, key=lambda x: -x[1])

    def get_report(self, threshold: int = 3) -> str | None:
        """Generate a report of potential N+1 issues."""
        candidates = self.get_n_plus_one_candidates(threshold)
        if not candidates:
            return None

        lines = [
            f"Potential N+1 query detected! {len(candidates)} pattern(s) found:",
            "",
        ]

        for pattern, count in candidates:
            lines.append(f"  [{count}x] {truncate_query(pattern)}")

            # Show sample parameters if available
            sample_queries = self.patterns[pattern][:3]
            for q in sample_queries:
                if q.parameters:
                    params_str = str(q.parameters)[:100]
                    lines.append(f"       params: {params_str}")

        lines.append("")
        lines.append(f"Total queries this request: {len(self.queries)}")

        return "\n".join(lines)


def normalize_query(statement: str) -> str:
    """Normalize a SQL query by replacing literal values with placeholders.

    This allows grouping similar queries that differ only in parameter values.
    """
    # Remove extra whitespace
    normalized = " ".join(statement.split())

    # Replace numeric literals
    normalized = re.sub(r"\b\d+\b", "?", normalized)

    # Replace string literals (single quotes)
    normalized = re.sub(r"'[^']*'", "?", normalized)

    # Replace IN clauses with multiple values: IN (?, ?, ?) -> IN (...)
    normalized = re.sub(r"IN\s*\(\s*\?(?:\s*,\s*\?)*\s*\)", "IN (...)", normalized)

    # Replace UUID-like patterns
    normalized = re.sub(
        r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
        "?",
        normalized,
        flags=re.IGNORECASE,
    )

    return normalized


def truncate_query(query: str, max_length: int = 120) -> str:
    """Truncate a query for display."""
    if len(query) <= max_length:
        return query
    return query[: max_length - 3] + "..."


def get_tracker() -> QueryTracker | None:
    """Get the query tracker for the current request."""
    if not has_request_context():
        return None
    return getattr(g, "_query_tracker", None)


def _is_enabled(app: Flask) -> bool:
    """Check if N+1 detection is enabled.

    Returns True if:
    - N_PLUS_ONE_ENABLED is explicitly True, OR
    - N_PLUS_ONE_ENABLED is None and app.debug is True
    """
    enabled = app.config.get("N_PLUS_ONE_ENABLED")
    if enabled is None:
        return app.debug
    return bool(enabled)


def init_n_plus_one_detector(app: Flask) -> None:
    """Initialize the N+1 query detector for a Flask app.

    The detector is only active when:
    - N_PLUS_ONE_ENABLED is explicitly set to True, OR
    - N_PLUS_ONE_ENABLED is not set (None) and app.debug is True

    To enable in production for testing, set N_PLUS_ONE_ENABLED=True.
    To disable in debug mode, set N_PLUS_ONE_ENABLED=False.
    """
    # Default configuration
    app.config.setdefault("N_PLUS_ONE_ENABLED", None)  # None = follow debug mode
    app.config.setdefault("N_PLUS_ONE_THRESHOLD", 3)
    app.config.setdefault("N_PLUS_ONE_LOG_LEVEL", "WARNING")
    app.config.setdefault("N_PLUS_ONE_RAISE", False)

    @app.before_request
    def start_query_tracking() -> None:
        """Start tracking queries for this request."""
        if not _is_enabled(app):
            return
        g._query_tracker = QueryTracker()

    @app.after_request
    def check_n_plus_one(response):
        """Check for N+1 issues after the request."""
        if not _is_enabled(app):
            return response

        tracker = get_tracker()
        if not tracker:
            return response

        threshold = app.config["N_PLUS_ONE_THRESHOLD"]
        report = tracker.get_report(threshold)

        if report:
            if app.config["N_PLUS_ONE_RAISE"]:
                raise NPlusOneDetectedError(report)

            log_level = app.config["N_PLUS_ONE_LOG_LEVEL"].upper()
            if log_level == "WARNING":
                logger.warning(report)
            elif log_level == "ERROR":
                logger.error(report)
            elif log_level == "INFO":
                logger.info(report)
            else:
                logger.debug(report)

        return response

    # Register SQLAlchemy event listener
    @event.listens_for(Engine, "before_cursor_execute")
    def receive_before_cursor_execute(
        conn, cursor, statement, parameters, context, executemany
    ):
        """Track each query execution."""
        tracker = get_tracker()
        if tracker and not executemany:
            # Skip certain system queries
            stmt_upper = statement.upper().strip()
            if not any(
                stmt_upper.startswith(prefix)
                for prefix in ("PRAGMA", "SAVEPOINT", "RELEASE", "ROLLBACK TO")
            ):
                tracker.add_query(statement, parameters)


class NPlusOneDetectedError(Exception):
    """Raised when N+1 query pattern is detected and N_PLUS_ONE_RAISE is True."""



# Convenience function for testing
def get_query_count() -> int:
    """Get the number of queries executed in the current request."""
    tracker = get_tracker()
    return len(tracker.queries) if tracker else 0


def get_query_stats() -> dict:
    """Get query statistics for the current request."""
    tracker = get_tracker()
    if not tracker:
        return {"total": 0, "patterns": 0, "potential_n_plus_one": []}

    return {
        "total": len(tracker.queries),
        "patterns": len(tracker.patterns),
        "potential_n_plus_one": tracker.get_n_plus_one_candidates(),
    }
