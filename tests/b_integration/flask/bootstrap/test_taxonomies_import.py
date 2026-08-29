# Copyright (c) 2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Loading the ontologies must never destroy what it can't replace.

Same defect as bugs #0287 / #0288 on the countries, one table over:
`import_taxonomies` deleted every `TaxonomyEntry` and committed before
parsing `Ontologies.ods`, and `ONTOLOGY_SRC` was resolved against the
current working directory. Run from anywhere but the repository root
— a worker, a service unit, a cron — the delete landed and the read
then raised, leaving `tax_taxonomy` empty for good.

The consequence is not cosmetic: an empty taxonomy table blanks every
KYC dropdown and every ciblage filter, which is the shape of ticket
#0320.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

import pytest
from sqlalchemy import delete, select

from app.flask.bootstrap.ontologies import ONTOLOGY_SRC, import_taxonomies
from app.services.taxonomies import TaxonomyEntry

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path


@pytest.fixture
def sentinel(db) -> Iterator[str]:
    """Commit one taxonomy row, yield its name, then remove it.

    The `db` fixture is session-wide and does NOT roll back, so a
    committed row would otherwise leak into every later test —
    `get_taxonomy("langue")` is read by the KYC ontology cache and by
    the ciblage selectors, and an extra entry breaks their
    expectations. Hence: unique name (so concurrent leftovers can't
    be mistaken for ours) and an explicit teardown.
    """
    name = f"Sentinelle-{uuid.uuid4().hex[:8]}"
    db.session.add(
        TaxonomyEntry(
            taxonomy_name="langue",
            name=name,
            value=name,
            category="",
            seq=0,
        )
    )
    db.session.commit()
    try:
        yield name
    finally:
        db.session.execute(delete(TaxonomyEntry).where(TaxonomyEntry.name == name))
        db.session.commit()


def survives(db, name: str) -> bool:
    stmt = select(TaxonomyEntry.id).where(TaxonomyEntry.name == name)
    return db.session.scalars(stmt).first() is not None


class TestOntologySource:
    def test_source_path_is_absolute(self) -> None:
        """A CWD-relative path is what made the loss reachable."""
        assert ONTOLOGY_SRC.is_absolute()

    def test_source_ships_with_the_repository(self) -> None:
        assert ONTOLOGY_SRC.is_file(), f"missing bootstrap data: {ONTOLOGY_SRC}"


class TestImportTaxonomies:
    def test_missing_file_leaves_the_table_alone(
        self, db, sentinel: str, tmp_path: Path
    ) -> None:
        """The regression itself: no source, no destruction."""
        with pytest.raises(FileNotFoundError):
            import_taxonomies(tmp_path / "does-not-exist.ods")

        assert survives(db, sentinel)

    def test_unreadable_file_leaves_the_table_alone(
        self, db, sentinel: str, tmp_path: Path
    ) -> None:
        """A truncated or corrupted workbook — a half-finished upload,
        say — must fail before the delete, not after it."""
        broken = tmp_path / "Ontologies.ods"
        broken.write_text("this is not a spreadsheet")

        with pytest.raises(Exception, match=r".*"):
            import_taxonomies(broken)

        assert survives(db, sentinel)
