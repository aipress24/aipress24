# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Tests for N+1 query detection middleware."""

from __future__ import annotations

import pytest

from app.flask.lib.n_plus_one_detector import (
    QueryTracker,
    normalize_query,
    truncate_query,
)


class TestNormalizeQuery:
    """Tests for query normalization."""

    def test_normalize_numeric_literals(self):
        query = "SELECT * FROM users WHERE id = 123"
        assert normalize_query(query) == "SELECT * FROM users WHERE id = ?"

    def test_normalize_string_literals(self):
        query = "SELECT * FROM users WHERE name = 'John'"
        assert normalize_query(query) == "SELECT * FROM users WHERE name = ?"

    def test_normalize_in_clause(self):
        query = "SELECT * FROM users WHERE id IN (1, 2, 3)"
        assert normalize_query(query) == "SELECT * FROM users WHERE id IN (...)"

    def test_normalize_uuid(self):
        query = "SELECT * FROM users WHERE uuid = '550e8400-e29b-41d4-a716-446655440000'"
        assert normalize_query(query) == "SELECT * FROM users WHERE uuid = ?"

    def test_normalize_whitespace(self):
        query = "SELECT   *   FROM   users   WHERE   id = 1"
        assert normalize_query(query) == "SELECT * FROM users WHERE id = ?"

    def test_normalize_complex_query(self):
        query = """
            SELECT u.*, o.name
            FROM users u
            JOIN organisations o ON u.org_id = o.id
            WHERE u.id = 42 AND o.name = 'Acme Corp'
        """
        expected = "SELECT u.*, o.name FROM users u JOIN organisations o ON u.org_id = o.id WHERE u.id = ? AND o.name = ?"
        assert normalize_query(query) == expected


class TestTruncateQuery:
    """Tests for query truncation."""

    def test_short_query_unchanged(self):
        query = "SELECT * FROM users"
        assert truncate_query(query, 50) == query

    def test_long_query_truncated(self):
        query = "SELECT * FROM users WHERE " + "x" * 100
        result = truncate_query(query, 50)
        assert len(result) == 50
        assert result.endswith("...")


class TestQueryTracker:
    """Tests for the QueryTracker class."""

    def test_add_query(self):
        tracker = QueryTracker()
        tracker.add_query("SELECT * FROM users WHERE id = 1", None)
        assert len(tracker.queries) == 1

    def test_add_multiple_queries(self):
        tracker = QueryTracker()
        tracker.add_query("SELECT * FROM users WHERE id = 1", None)
        tracker.add_query("SELECT * FROM users WHERE id = 2", None)
        tracker.add_query("SELECT * FROM users WHERE id = 3", None)
        assert len(tracker.queries) == 3

    def test_patterns_grouped(self):
        tracker = QueryTracker()
        tracker.add_query("SELECT * FROM users WHERE id = 1", None)
        tracker.add_query("SELECT * FROM users WHERE id = 2", None)
        tracker.add_query("SELECT * FROM posts WHERE id = 1", None)

        # Should have 2 patterns
        assert len(tracker.patterns) == 2

        # Users pattern should have 2 queries
        users_pattern = "SELECT * FROM users WHERE id = ?"
        assert len(tracker.patterns[users_pattern]) == 2

    def test_n_plus_one_detection_below_threshold(self):
        tracker = QueryTracker()
        tracker.add_query("SELECT * FROM users WHERE id = 1", None)
        tracker.add_query("SELECT * FROM users WHERE id = 2", None)

        candidates = tracker.get_n_plus_one_candidates(threshold=3)
        assert len(candidates) == 0

    def test_n_plus_one_detection_at_threshold(self):
        tracker = QueryTracker()
        tracker.add_query("SELECT * FROM users WHERE id = 1", None)
        tracker.add_query("SELECT * FROM users WHERE id = 2", None)
        tracker.add_query("SELECT * FROM users WHERE id = 3", None)

        candidates = tracker.get_n_plus_one_candidates(threshold=3)
        assert len(candidates) == 1
        assert candidates[0][1] == 3  # count

    def test_n_plus_one_detection_above_threshold(self):
        tracker = QueryTracker()
        for i in range(10):
            tracker.add_query(f"SELECT * FROM users WHERE id = {i}", None)

        candidates = tracker.get_n_plus_one_candidates(threshold=3)
        assert len(candidates) == 1
        assert candidates[0][1] == 10

    def test_multiple_n_plus_one_patterns(self):
        tracker = QueryTracker()
        for i in range(5):
            tracker.add_query(f"SELECT * FROM users WHERE id = {i}", None)
        for i in range(4):
            tracker.add_query(f"SELECT * FROM posts WHERE user_id = {i}", None)

        candidates = tracker.get_n_plus_one_candidates(threshold=3)
        assert len(candidates) == 2
        # Should be sorted by count descending
        assert candidates[0][1] == 5
        assert candidates[1][1] == 4

    def test_disabled_tracker(self):
        tracker = QueryTracker(enabled=False)
        tracker.add_query("SELECT * FROM users WHERE id = 1", None)
        assert len(tracker.queries) == 0

    def test_report_none_when_no_issues(self):
        tracker = QueryTracker()
        tracker.add_query("SELECT * FROM users WHERE id = 1", None)
        assert tracker.get_report(threshold=3) is None

    def test_report_generated_when_issues_found(self):
        tracker = QueryTracker()
        for i in range(5):
            tracker.add_query(f"SELECT * FROM users WHERE id = {i}", None)

        report = tracker.get_report(threshold=3)
        assert report is not None
        assert "N+1 query detected" in report
        assert "[5x]" in report
        assert "SELECT * FROM users" in report


class TestQueryTrackerWithParameters:
    """Tests for query tracking with parameters."""

    def test_tracks_parameters(self):
        tracker = QueryTracker()
        tracker.add_query("SELECT * FROM users WHERE id = ?", (1,))
        tracker.add_query("SELECT * FROM users WHERE id = ?", (2,))

        assert tracker.queries[0].parameters == (1,)
        assert tracker.queries[1].parameters == (2,)

    def test_report_includes_sample_parameters(self):
        tracker = QueryTracker()
        for i in range(5):
            tracker.add_query("SELECT * FROM users WHERE id = ?", (i,))

        report = tracker.get_report(threshold=3)
        assert "params:" in report
