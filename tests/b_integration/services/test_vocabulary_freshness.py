# Copyright (c) 2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""An ontology edit reaches the NEWSROOM forms on the next request.

The vocabularies are read straight from the database on every call —
see `local-notes/decisions/2026-09-03-taxonomy-vocabulary-cache.md`.
These tests hold that guarantee, which is the one `expert_selectors.py`
already documents for the ciblage: "adding / editing an entry in
/admin/ontology takes effect on the next request".

They fail as soon as a cache is put back without cross-process
invalidation, which is the point.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import app.settings.vocabularies as voc
from app.services.taxonomies import TaxonomyEntry

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

TAXONOMY = "genres"


def _add_genre(db_session: Session, name: str) -> TaxonomyEntry:
    entry = TaxonomyEntry(
        taxonomy_name=TAXONOMY, name=name, category="", value=name, seq=999
    )
    db_session.add(entry)
    db_session.flush()
    return entry


def test_an_added_entry_shows_up_at_once(db_session: Session, app) -> None:
    with app.test_request_context():
        before = voc.get_genres()
        _add_genre(db_session, "Brand-New-Genre")
        after = voc.get_genres()

    assert "Brand-New-Genre" not in before
    assert "Brand-New-Genre" in after


def test_a_removed_entry_disappears_at_once(db_session: Session, app) -> None:
    with app.test_request_context():
        entry = _add_genre(db_session, "Short-Lived-Genre")
        assert "Short-Lived-Genre" in voc.get_genres()

        db_session.delete(entry)
        db_session.flush()

        assert "Short-Lived-Genre" not in voc.get_genres()


def test_an_edited_label_shows_up_at_once(db_session: Session, app) -> None:
    """An in-place UPDATE, which no cheap version stamp would catch."""
    with app.test_request_context():
        entry = _add_genre(db_session, "Before-Rename")
        assert "Before-Rename" in voc.get_genres()

        entry.name = "After-Rename"
        db_session.flush()

        genres = voc.get_genres()
        assert "After-Rename" in genres
        assert "Before-Rename" not in genres


def test_each_vocabulary_reads_its_own_taxonomy(db_session: Session, app) -> None:
    """All six go through one `get_vocab(name)`; the name is what selects."""
    with app.test_request_context():
        _add_genre(db_session, "Isolated-Genre")

        assert "Isolated-Genre" in voc.get_genres()
        assert "Isolated-Genre" not in voc.get_sections()
        assert "Isolated-Genre" not in voc.get_topics()
        assert "Isolated-Genre" not in voc.get_news_sectors()
