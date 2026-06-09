# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Tests for the ``flask search`` CLI commands.

``rebuild`` is covered in ``test_jobs_and_rebuild.py``; here we add
``status`` and ``query`` which had no coverage. Each test injects a
RAM-backed engine via the SVCS container so we can pre-seed docs
without touching the database.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

import pytest
import svcs.flask
from wesh.backends.filedb.filestore import RamStorage

from app.modules.search.cli import query, status
from app.modules.search.engine import SearchEngine

if TYPE_CHECKING:
    from collections.abc import Iterator


@pytest.fixture
def test_engine(app) -> Iterator[SearchEngine]:
    engine = SearchEngine(RamStorage())
    previous = svcs.flask.overwrite_value(SearchEngine, engine)
    try:
        yield engine
    finally:
        if previous is not None:
            svcs.flask.overwrite_value(SearchEngine, previous)


def _doc(*, type: str, pk: int, title: str, text: str = "") -> dict:
    return {
        "type": type,
        "id": f"{type}:{pk}",
        "title": title,
        "text": text or title,
        "summary": "",
        "url": f"/{type}/{pk}",
        "timestamp": datetime(2026, 1, 1, tzinfo=UTC),
        "tags": "",
    }


class TestSearchStatusCli:
    def test_empty_index_reports_zeros(self, app, test_engine):
        runner = app.test_cli_runner()
        result = runner.invoke(status)
        assert result.exit_code == 0, result.output
        assert "Total:" in result.output
        assert "0" in result.output
        # Every doc-type should appear in the breakdown (Groups retirés
        # le 2026-05-21).
        for type_name in (
            "article",
            "press_release",
            "event",
            "user",
            "organisation",
        ):
            assert type_name in result.output

    def test_status_reports_per_type_counts(self, app, test_engine):
        test_engine.upsert(_doc(type="article", pk=1, title="x"))
        test_engine.upsert(_doc(type="article", pk=2, title="y"))
        test_engine.upsert(_doc(type="event", pk=10, title="z"))

        runner = app.test_cli_runner()
        result = runner.invoke(status)

        assert result.exit_code == 0, result.output
        assert "Total:" in result.output
        # The breakdown should mention article and event with their counts.
        lines = [line.strip() for line in result.output.splitlines()]
        article_line = next(line for line in lines if "article" in line)
        event_line = next(line for line in lines if "event" in line)
        assert "2" in article_line
        assert "1" in event_line


class TestSearchQueryCli:
    def test_query_with_no_hits(self, app, test_engine):
        runner = app.test_cli_runner()
        result = runner.invoke(query, ["nonexistent_term_xyz"])
        assert result.exit_code == 0, result.output
        assert "No results" in result.output

    def test_query_returns_matching_hits(self, app, test_engine):
        test_engine.upsert(
            _doc(
                type="article",
                pk=1,
                title="Python at scale",
                text="Production python services.",
            )
        )
        test_engine.upsert(
            _doc(
                type="event",
                pk=10,
                title="Conference",
                text="A networking event.",
            )
        )

        runner = app.test_cli_runner()
        result = runner.invoke(query, ["python"])

        assert result.exit_code == 0, result.output
        assert "Python at scale" in result.output
        assert "article:1" in result.output
        assert "Conference" not in result.output  # event doesn't match

    def test_query_with_type_filter(self, app, test_engine):
        test_engine.upsert(
            _doc(type="article", pk=1, title="Article python", text="...")
        )
        test_engine.upsert(_doc(type="event", pk=2, title="Event python", text="..."))

        runner = app.test_cli_runner()
        result = runner.invoke(query, ["python", "--type", "event"])

        assert result.exit_code == 0, result.output
        assert "Event python" in result.output
        assert "Article python" not in result.output

    def test_query_respects_limit_option(self, app, test_engine):
        for i in range(5):
            test_engine.upsert(
                _doc(type="article", pk=i, title=f"Doc {i} python", text="python body")
            )

        runner = app.test_cli_runner()
        result = runner.invoke(query, ["python", "--limit", "2"])

        assert result.exit_code == 0, result.output
        # Each hit prints a "Doc N python" line in bold; count them.
        hit_lines = [line for line in result.output.splitlines() if "Doc " in line]
        assert len(hit_lines) == 2
