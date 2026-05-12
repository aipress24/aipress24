"""Wesh-backed search engine service.

Owns a single wesh index keyed off the app's SQLAlchemy database URL.
Exposes the minimal CRUD surface needed by the rest of the search
module (receivers, jobs, views). Indexing is upsert-by-id so callers
don't need to track insert-vs-update; deletion is by primary id.

The engine is decoupled from Flask: it takes a Storage instance, so
tests can pass a ``RamStorage`` or a SQLite-backed ``SQLAlchemyStorage``
without an app context. The ``svcs_factory`` classmethod is the bridge
to the SVCS container at runtime.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from flask_super.decorators import service
from wesh.qparser import MultifieldParser
from wesh.query import And, Or, Term

from .schema import SCHEMA

if TYPE_CHECKING:
    from svcs import Container
    from wesh.backends.filedb.filestore import Storage


@service
class SearchEngine:
    """Thin wrapper around a wesh index.

    One index per ``Storage``. The index is opened lazily on first
    access; ``storage.create()`` must have been called before any
    operation that needs the underlying tables (this is the caller's
    responsibility; ``svcs_factory`` handles it for the Flask path).
    """

    def __init__(self, storage: Storage) -> None:
        self._storage = storage
        self._index: Any = None  # whoosh.index.Index, lazy

    @classmethod
    def svcs_factory(cls, container: Container) -> SearchEngine:
        from flask import current_app
        from wesh.backends.sql.storage import SQLAlchemyStorage

        url = current_app.config["SQLALCHEMY_DATABASE_URI"]
        storage = SQLAlchemyStorage(url).create()
        return cls(storage)

    # ── Index lifecycle ─────────────────────────────────────────────

    def _get_index(self) -> Any:
        if self._index is None:
            if self._storage.index_exists():
                self._index = self._storage.open_index(schema=SCHEMA)
            else:
                self._index = self._storage.create_index(SCHEMA)
        return self._index

    # ── CRUD ────────────────────────────────────────────────────────

    def upsert(self, doc: dict[str, Any]) -> None:
        """Insert or update a document. The schema's ``id`` field is
        ``unique=True``, so wesh replaces an existing doc with the same id.
        """
        ix = self._get_index()
        with ix.writer() as w:
            w.update_document(**doc)

    def delete(self, doc_id: str) -> None:
        """Remove a document by composite id (``"<type>:<pk>"``). No-op
        if the id is not in the index.
        """
        ix = self._get_index()
        with ix.writer() as w:
            w.delete_by_term("id", doc_id)

    def reset(self) -> None:
        """Drop every document from the index, keeping the schema.

        Used by ``flask search rebuild`` to start from a clean slate
        before re-walking the database. Cheaper than dropping and
        recreating the storage tables.
        """
        from wesh.writing import CLEAR

        ix = self._get_index()
        writer = ix.writer()
        writer.commit(mergetype=CLEAR)

    def doc_count(self, *, type: str | None = None) -> int:
        """Return the number of indexed documents, optionally filtered
        by ``type``. Used by the ``status`` CLI command.
        """
        ix = self._get_index()
        with ix.searcher() as s:
            if type is None:
                return s.doc_count()
            from wesh.query import Term

            return s.search(Term("type", type), limit=None).estimated_length()

    # ── Query ───────────────────────────────────────────────────────

    def search(
        self,
        qs: str,
        *,
        type: str | list[str] | None = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """Run a BM25 search over title + text. ``type`` can be a single
        discriminator (``"article"``), a list of them (one filter
        covering several index types, e.g. all marketplace kinds), or
        ``None`` to search every type.
        """
        ix = self._get_index()
        query = self._build_query(qs, type=type)
        with ix.searcher() as s:
            results = s.search(query, limit=limit)
            return [dict(hit) for hit in results]

    def count(self, qs: str, *, type: str | list[str] | None = None) -> int:
        """Return the number of documents matching ``qs`` (optionally
        filtered by ``type``). Used by the sidebar to show per-type
        counts without materialising the hits.
        """
        ix = self._get_index()
        query = self._build_query(qs, type=type)
        with ix.searcher() as s:
            return s.search(query, limit=None).estimated_length()

    def _build_query(
        self, qs: str, *, type: str | list[str] | None
    ) -> Any:
        parser = MultifieldParser(["title", "text"], schema=SCHEMA)
        query = parser.parse(qs)
        if type is None:
            return query
        if isinstance(type, str):
            return And([query, Term("type", type)])
        # list[str] — OR the discriminators, AND with the text query
        return And([query, Or([Term("type", t) for t in type])])
