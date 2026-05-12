# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Unit tests for the wesh-backed SearchEngine service."""

from __future__ import annotations

import tempfile
from datetime import UTC, datetime
from pathlib import Path

import pytest
from wesh.backends.filedb.filestore import RamStorage
from wesh.backends.sql.storage import SQLAlchemyStorage

from app.modules.search.engine import SearchEngine


def _doc(
    *,
    type: str,
    pk: int,
    title: str,
    text: str,
    summary: str = "",
    tags: str = "",
    when: datetime | None = None,
) -> dict:
    return {
        "type": type,
        "id": f"{type}:{pk}",
        "title": title,
        "text": text,
        "summary": summary,
        "url": f"/{type}/{pk}",
        "timestamp": when or datetime(2026, 1, 1, tzinfo=UTC),
        "tags": tags,
    }


@pytest.fixture
def engine() -> SearchEngine:
    return SearchEngine(RamStorage())


@pytest.fixture
def populated_engine(engine: SearchEngine) -> SearchEngine:
    engine.upsert(
        _doc(
            type="article",
            pk=1,
            title="Python at scale",
            text="A long-form piece on running python services in production.",
            summary="Production python.",
            tags="python,production",
        )
    )
    engine.upsert(
        _doc(
            type="article",
            pk=2,
            title="Rust for python developers",
            text="A primer on rust idioms for people coming from python.",
            summary="Rust for pythonistas.",
            tags="rust,python",
        )
    )
    engine.upsert(
        _doc(
            type="event",
            pk=10,
            title="PyConFR 2026",
            text="Annual french python conference.",
            summary="The conference.",
            tags="python,conference",
        )
    )
    return engine


class TestSearchEngineCRUD:
    def test_upsert_then_search_finds_doc(self, engine: SearchEngine) -> None:
        engine.upsert(
            _doc(type="article", pk=1, title="alfa bravo", text="charlie delta")
        )

        hits = engine.search("bravo")

        assert [h["id"] for h in hits] == ["article:1"]
        assert hits[0]["title"] == "alfa bravo"
        assert hits[0]["url"] == "/article/1"

    def test_upsert_is_idempotent_on_same_id(self, engine: SearchEngine) -> None:
        engine.upsert(_doc(type="article", pk=1, title="first version", text="alfa"))
        engine.upsert(_doc(type="article", pk=1, title="second version", text="bravo"))

        hits_first = engine.search("first")
        hits_second = engine.search("second")

        assert hits_first == []
        assert [h["title"] for h in hits_second] == ["second version"]

    def test_delete_removes_doc(self, engine: SearchEngine) -> None:
        engine.upsert(_doc(type="article", pk=1, title="alfa", text="bravo"))
        assert engine.search("bravo")

        engine.delete("article:1")

        assert engine.search("bravo") == []

    def test_delete_unknown_id_is_noop(self, engine: SearchEngine) -> None:
        # Should not raise.
        engine.delete("article:999")


class TestSearchEngineRanking:
    def test_bm25_orders_by_relevance(
        self, populated_engine: SearchEngine
    ) -> None:
        hits = populated_engine.search("python")

        # All three docs mention python; the title match on
        # "Python at scale" should outrank the body-only matches.
        ids = [h["id"] for h in hits]
        assert ids[0] == "article:1"
        assert set(ids) == {"article:1", "article:2", "event:10"}

    def test_filter_by_type_restricts_results(
        self, populated_engine: SearchEngine
    ) -> None:
        hits = populated_engine.search("python", type="event")

        assert [h["id"] for h in hits] == ["event:10"]

    def test_filter_by_type_excludes_others(
        self, populated_engine: SearchEngine
    ) -> None:
        hits = populated_engine.search("python", type="article")

        assert {h["id"] for h in hits} == {"article:1", "article:2"}
        assert all(h["type"] == "article" for h in hits)

    def test_limit_caps_result_count(self, populated_engine: SearchEngine) -> None:
        hits = populated_engine.search("python", limit=1)

        assert len(hits) == 1


class TestSearchEngineSqlStorage:
    """Smoke-check that the SearchEngine works end-to-end against the
    SQL-backed storage, not just RAM. Sqlite is enough; the Postgres
    path is exercised in integration tests later in CI.
    """

    def test_roundtrip_against_sqlite_storage(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            url = f"sqlite:///{Path(td) / 'phase2.db'}"
            storage = SQLAlchemyStorage(url).create()
            engine = SearchEngine(storage)

            engine.upsert(
                _doc(
                    type="article",
                    pk=42,
                    title="The answer",
                    text="forty two is the answer to life",
                )
            )
            engine.upsert(
                _doc(
                    type="event",
                    pk=7,
                    title="A different topic",
                    text="nothing about answers here",
                )
            )

            hits = engine.search("answer", type="article")

            assert [h["id"] for h in hits] == ["article:42"]
