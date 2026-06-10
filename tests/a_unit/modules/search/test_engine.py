# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Unit tests for the wesh-backed SearchEngine service."""

from __future__ import annotations

import tempfile
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest
from wesh.backends.filedb.filestore import RamStorage
from wesh.backends.sql.storage import SQLAlchemyStorage

from app.modules.search.engine import SearchEngine


def _unique_indexname() -> str:
    """Give each engine a unique on-disk segment dir.

    wesh's writer uses `/<tempdir>/<indexname>.tmp/` for segment
    finalisation. That dir is shared across processes — under
    pytest-xdist parallel runs concurrent workers writing to
    `/tmp/MAIN.tmp/` race on file create/delete and produce
    `FileNotFoundError`. A per-engine random name avoids the clash."""
    return f"test_{uuid4().hex[:12]}"


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
    return SearchEngine(RamStorage(), indexname=_unique_indexname())


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
    def test_bm25_orders_by_relevance(self, populated_engine: SearchEngine) -> None:
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
            engine = SearchEngine(storage, indexname=_unique_indexname())

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


class TestSearchEngineEdgeCases:
    def test_reset_clears_all_docs(self, populated_engine: SearchEngine) -> None:
        assert populated_engine.search("python")  # warm-up: there are docs
        populated_engine.reset()
        assert populated_engine.search("python") == []
        assert populated_engine.doc_count() == 0

    def test_reset_keeps_schema_so_engine_still_usable(
        self, populated_engine: SearchEngine
    ) -> None:
        populated_engine.reset()
        populated_engine.upsert(
            _doc(type="article", pk=999, title="post-reset", text="post-reset body")
        )
        hits = populated_engine.search("post-reset")
        assert [h["id"] for h in hits] == ["article:999"]

    def test_count_matches_search_for_small_corpus(
        self, populated_engine: SearchEngine
    ) -> None:
        assert populated_engine.count("python") == len(
            populated_engine.search("python", limit=100)
        )

    def test_count_with_type_filter_matches_search(
        self, populated_engine: SearchEngine
    ) -> None:
        assert populated_engine.count("python", type="article") == len(
            populated_engine.search("python", type="article", limit=100)
        )

    def test_list_type_filter_unions_types(
        self, populated_engine: SearchEngine
    ) -> None:
        """When ``type`` is a list, hits include docs of any matching type."""
        article_event_hits = populated_engine.search(
            "python", type=["article", "event"]
        )
        article_only_hits = populated_engine.search("python", type="article")
        event_only_hits = populated_engine.search("python", type="event")

        ids = {h["id"] for h in article_event_hits}
        assert ids == {h["id"] for h in article_only_hits} | {
            h["id"] for h in event_only_hits
        }

    def test_empty_list_type_filter_returns_nothing(
        self, populated_engine: SearchEngine
    ) -> None:
        """A list filter with no allowed types is a contradiction —
        OR of nothing matches nothing."""
        assert populated_engine.search("python", type=[]) == []

    def test_unknown_type_filter_returns_empty(
        self, populated_engine: SearchEngine
    ) -> None:
        assert populated_engine.search("python", type="nonexistent") == []

    def test_delete_unknown_id_does_not_affect_others(
        self, populated_engine: SearchEngine
    ) -> None:
        before = populated_engine.doc_count()
        populated_engine.delete("article:99999999")
        assert populated_engine.doc_count() == before

    def test_search_with_limit_larger_than_corpus(
        self, populated_engine: SearchEngine
    ) -> None:
        # Corpus has 3 docs total; asking for 100 should return at most 3.
        hits = populated_engine.search("python", limit=100)
        assert 1 <= len(hits) <= 3
