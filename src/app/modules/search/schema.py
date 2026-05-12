"""Unified wesh schema for the aipress24 search index.

One index, one schema, discriminated by the ``type`` field. The ``id``
is a composite ``"<type>:<pk>"`` string so that primary-key collisions
across SQLAlchemy tables don't conflict in the index.

Stored fields are returned in hit documents and drive the UI. Indexed
(but not stored) fields contribute to scoring only.
"""

from __future__ import annotations

from whoosh import fields

SCHEMA = fields.Schema(
    type=fields.KEYWORD(stored=True, lowercase=True, facet=True),
    id=fields.ID(stored=True, unique=True),
    title=fields.TEXT(stored=True),
    text=fields.TEXT,
    summary=fields.STORED,
    url=fields.STORED,
    timestamp=fields.DATETIME(stored=True, sortable=True),
    tags=fields.KEYWORD(stored=True, commas=True, facet=True),
)
