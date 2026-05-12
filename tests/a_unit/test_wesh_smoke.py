"""Smoke tests for the vendored wesh (Whoosh-Reloaded) search engine.

These tests prove that the package is importable, that an in-memory
index works, and that the SQLAlchemy-backed storage works against
SQLite. They are intentionally tiny — full coverage lives in
``vendor/wesh/tests/``. The goal here is just to confirm the wiring
is alive at the aipress24 level.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from wesh import fields
from wesh.backends.filedb.filestore import RamStorage
from wesh.backends.sql.storage import SQLAlchemyStorage
from wesh.qparser import QueryParser

SCHEMA = fields.Schema(
    id=fields.ID(stored=True, unique=True),
    title=fields.TEXT(stored=True),
    body=fields.TEXT,
)


def test_wesh_ram_storage_roundtrip() -> None:
    ix = RamStorage().create_index(SCHEMA)

    with ix.writer() as w:
        w.add_document(id="1", title="alfa", body="bravo charlie")
        w.add_document(id="2", title="delta", body="echo foxtrot")

    with ix.searcher() as s:
        q = QueryParser("body", schema=SCHEMA).parse("bravo")
        hits = list(s.search(q))
        assert [h["id"] for h in hits] == ["1"]


def test_wesh_sqlalchemy_storage_roundtrip() -> None:
    with tempfile.TemporaryDirectory() as td:
        db_path = Path(td) / "smoke.db"
        url = f"sqlite:///{db_path}"

        storage = SQLAlchemyStorage(url).create()
        ix = storage.create_index(SCHEMA)

        with ix.writer() as w:
            w.add_document(id="1", title="alfa", body="bravo charlie")
            w.add_document(id="2", title="delta", body="echo foxtrot")

        with ix.searcher() as s:
            q = QueryParser("body", schema=SCHEMA).parse("bravo")
            hits = list(s.search(q))
            assert [h["id"] for h in hits] == ["1"]
