# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Mock-free unit tests for the N+1 query detector internals.

The existing test module (``tests/a_unit/flask/test_n_plus_one_detector.py``)
covers the pure aggregator (``QueryTracker``, ``normalize_query``,
``truncate_query``). This file pushes coverage on the *Flask-bound* helpers
that wrap the aggregator :

- ``_is_enabled`` — the three-state config switch (None / True / False)
- ``_should_track_query`` — filter for system queries (PRAGMA, SAVEPOINT…)
- ``_log_report`` — log-level routing into loguru
- ``get_tracker`` / ``get_query_count`` / ``get_query_stats`` — request-bound
  accessors (with and without an active request context)
- ``_check_n_plus_one`` — after-request hook, both the "log" and "raise"
  branches

Strategy : we use a real bare ``Flask`` app and ``test_request_context`` to
exercise the request-bound helpers. No stand-in libraries are used : log
capture goes through a ``loguru`` sink that appends to a real list, exactly
the kind of "real fake collaborator" the project's mock-free pattern allows.
"""

from __future__ import annotations

import pytest
from flask import Flask, g
from loguru import logger

from app.flask.lib.n_plus_one_detector import (
    NPlusOneDetectedError,
    QueryTracker,
    _check_n_plus_one,
    _is_enabled,
    _log_report,
    _should_track_query,
    get_query_count,
    get_query_stats,
    get_tracker,
)

# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------


def make_app(debug: bool = False, **config: object) -> Flask:
    """Build a minimal Flask app with the detector's default config keys.

    Mirrors what ``init_n_plus_one_detector`` would have installed, but
    without registering the module-level SQLAlchemy ``Engine`` event
    listener (which would leak across the test suite).
    """
    app = Flask(__name__)
    app.debug = debug
    app.config.setdefault("N_PLUS_ONE_ENABLED", None)
    app.config.setdefault("N_PLUS_ONE_THRESHOLD", 3)
    app.config.setdefault("N_PLUS_ONE_LOG_LEVEL", "WARNING")
    app.config.setdefault("N_PLUS_ONE_RAISE", False)
    app.config.update(config)
    return app


class LogSink:
    """Append-only real list used as a loguru sink.

    Acts as a Pattern C "real fake collaborator" — it implements the
    sink protocol (callable taking a message) and stores the rendered
    records. Tests assert on the *state* of this list, not on a recorded
    call sequence to a mock.
    """

    def __init__(self) -> None:
        self.records: list[tuple[str, str]] = []

    def __call__(self, message) -> None:
        record = message.record
        self.records.append((record["level"].name, record["message"]))


# ----------------------------------------------------------------------
# _is_enabled
# ----------------------------------------------------------------------


class TestIsEnabled:
    """Three-state switch : None → follow debug, True/False → explicit."""

    @pytest.mark.parametrize(
        ("enabled", "debug", "expected"),
        [
            (None, True, True),  # follow debug
            (None, False, False),  # follow debug
            (True, False, True),  # explicit override (production)
            (True, True, True),
            (False, True, False),  # explicit disable in debug
            (False, False, False),
            (1, False, True),  # truthy non-bool coerced
            (0, True, False),  # falsy non-bool coerced
        ],
    )
    def test_three_state_switch(self, enabled, debug, expected) -> None:
        app = make_app(debug=debug, N_PLUS_ONE_ENABLED=enabled)
        assert _is_enabled(app) is expected


# ----------------------------------------------------------------------
# _should_track_query
# ----------------------------------------------------------------------


class TestShouldTrackQuery:
    """Filter out cursor-management statements that are not user SQL."""

    @pytest.mark.parametrize(
        "statement",
        [
            "SELECT * FROM users",
            "INSERT INTO posts VALUES (?)",
            "UPDATE users SET name = ?",
            "DELETE FROM events WHERE id = ?",
            "  select 1",  # leading whitespace + lower-case still tracked
        ],
    )
    def test_tracks_user_queries(self, statement) -> None:
        assert _should_track_query(statement) is True

    @pytest.mark.parametrize(
        "statement",
        [
            "PRAGMA foreign_keys = ON",
            "pragma table_info(users)",  # case-insensitive
            "SAVEPOINT sp_1",
            "RELEASE sp_1",
            "ROLLBACK TO sp_1",
            "  PRAGMA journal_mode = WAL",  # leading whitespace
        ],
    )
    def test_skips_system_queries(self, statement) -> None:
        assert _should_track_query(statement) is False


# ----------------------------------------------------------------------
# _log_report
# ----------------------------------------------------------------------


class TestLogReport:
    """Route the report to the requested loguru level."""

    @pytest.mark.parametrize(
        ("level_arg", "expected_level"),
        [
            ("WARNING", "WARNING"),
            ("warning", "WARNING"),
            ("ERROR", "ERROR"),
            ("error", "ERROR"),
            ("INFO", "INFO"),
            ("info", "INFO"),
            ("DEBUG", "DEBUG"),
            ("ANYTHING_ELSE", "DEBUG"),  # fallback
        ],
    )
    def test_level_routing(self, level_arg, expected_level) -> None:
        sink = LogSink()
        handler_id = logger.add(sink, level="DEBUG", format="{message}")
        try:
            _log_report("hello report", level_arg)
        finally:
            logger.remove(handler_id)

        assert sink.records, "expected at least one log record"
        assert sink.records[-1] == (expected_level, "hello report")


# ----------------------------------------------------------------------
# get_tracker / get_query_count / get_query_stats
# ----------------------------------------------------------------------


class TestRequestBoundAccessors:
    """Accessors that read from ``flask.g`` — must tolerate no-context."""

    def test_get_tracker_returns_none_outside_request(self) -> None:
        assert get_tracker() is None

    def test_get_query_count_zero_outside_request(self) -> None:
        assert get_query_count() == 0

    def test_get_query_stats_empty_outside_request(self) -> None:
        stats = get_query_stats()
        assert stats == {
            "total": 0,
            "patterns": 0,
            "potential_n_plus_one": [],
        }

    def test_get_tracker_none_when_no_tracker_installed(self) -> None:
        app = make_app()
        with app.test_request_context("/"):
            # No tracker attached to g
            assert get_tracker() is None
            assert get_query_count() == 0
            assert get_query_stats()["total"] == 0

    def test_accessors_with_tracker_installed(self) -> None:
        app = make_app()
        with app.test_request_context("/"):
            g._query_tracker = QueryTracker()
            for i in range(4):
                g._query_tracker.add_query(f"SELECT * FROM users WHERE id = {i}", None)
            # Unrelated single query forms a different pattern
            g._query_tracker.add_query("SELECT * FROM posts WHERE id = 1", None)

            assert get_tracker() is g._query_tracker
            assert get_query_count() == 5

            stats = get_query_stats()
            assert stats["total"] == 5
            assert stats["patterns"] == 2
            # Only the users pattern crosses the default threshold of 3
            assert stats["potential_n_plus_one"] == [
                ("SELECT * FROM users WHERE id = ?", 4)
            ]


# ----------------------------------------------------------------------
# _check_n_plus_one
# ----------------------------------------------------------------------


class TestCheckNPlusOne:
    """After-request hook : either log or raise depending on config."""

    def test_returns_response_when_no_tracker(self) -> None:
        app = make_app()
        sentinel = object()
        with app.test_request_context("/"):
            # No tracker installed on g
            assert _check_n_plus_one(app, sentinel) is sentinel

    def test_returns_response_when_below_threshold(self) -> None:
        app = make_app(N_PLUS_ONE_THRESHOLD=10)
        sentinel = object()
        sink = LogSink()
        handler_id = logger.add(sink, level="DEBUG", format="{message}")
        try:
            with app.test_request_context("/"):
                g._query_tracker = QueryTracker()
                for i in range(5):
                    g._query_tracker.add_query(
                        f"SELECT * FROM users WHERE id = {i}", None
                    )
                assert _check_n_plus_one(app, sentinel) is sentinel
        finally:
            logger.remove(handler_id)

        # Nothing logged because the report is None
        assert not any("N+1" in msg for _lvl, msg in sink.records)

    def test_logs_when_report_present(self) -> None:
        app = make_app(N_PLUS_ONE_LOG_LEVEL="ERROR")
        sentinel = object()
        sink = LogSink()
        handler_id = logger.add(sink, level="DEBUG", format="{message}")
        try:
            with app.test_request_context("/"):
                g._query_tracker = QueryTracker()
                for i in range(5):
                    g._query_tracker.add_query(
                        f"SELECT * FROM users WHERE id = {i}", None
                    )
                result = _check_n_plus_one(app, sentinel)
        finally:
            logger.remove(handler_id)

        assert result is sentinel
        error_records = [r for r in sink.records if r[0] == "ERROR"]
        assert error_records, "expected an ERROR-level record"
        assert "N+1 query detected" in error_records[-1][1]

    def test_raises_when_configured_to_raise(self) -> None:
        app = make_app(N_PLUS_ONE_RAISE=True)
        with app.test_request_context("/"):
            g._query_tracker = QueryTracker()
            for i in range(5):
                g._query_tracker.add_query(f"SELECT * FROM users WHERE id = {i}", None)
            with pytest.raises(NPlusOneDetectedError) as exc_info:
                _check_n_plus_one(app, object())

        assert "N+1 query detected" in str(exc_info.value)
