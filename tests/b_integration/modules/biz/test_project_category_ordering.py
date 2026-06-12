# Copyright (c) 2021-2026, Abilian SAS & TCA
# SPDX-License-Identifier: AGPL-3.0-only

"""Integration test for ticket #0202 — PROJETS/Type de projet ordering.

Erick (2026-06-11) :

> tu peux mettre dans le bon ordre PROJETS/Type de projet
> 1- Journalisme, 2-Communication, 3-Innovation. Merci.

The ontology already stores the canonical order via `TaxonomyEntry.seq`
(Journalisme=10, Communication=20, Innovation=30). The bug was that
`get_taxonomy(name)` in `services/taxonomies/_service.py` sorted rows
alphabetically by `name`, which surfaced them as
`Communication, Innovation, Journalisme` — the reverse of Erick's spec.

Fix : the projects view now reads through `get_full_taxonomy` (sorts
by `seq`) instead. Pin the ordering at b_integration : seed the table
with the three rows out-of-order, call `get_project_category_choices`,
assert the result matches the seq order.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from app.modules.biz.views.projects import get_project_category_choices
from app.services.taxonomies._models import TaxonomyEntry

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


_TAXONOMY_NAME = "type_projets"


@pytest.fixture
def _seed_type_projets_taxonomy(db_session: Session):
    """Insert the three canonical project categories with `seq` values
    Erick set in the admin (Journalisme=10, Communication=20,
    Innovation=30). Crucially, insert them in REVERSE alphabetical
    order so an accidental « sort by name » regression would surface
    them as Communication, Innovation, Journalisme — the exact bug
    pattern we're protecting against."""
    rows = [
        TaxonomyEntry(
            taxonomy_name=_TAXONOMY_NAME,
            name="Journalisme",
            value="journalisme",
            category="",
            seq=10,
        ),
        TaxonomyEntry(
            taxonomy_name=_TAXONOMY_NAME,
            name="Communication",
            value="communication",
            category="",
            seq=20,
        ),
        TaxonomyEntry(
            taxonomy_name=_TAXONOMY_NAME,
            name="Innovation",
            value="innovation",
            category="",
            seq=30,
        ),
    ]
    db_session.add_all(rows)
    db_session.flush()
    yield rows
    for row in rows:
        db_session.delete(row)
    db_session.flush()


@pytest.mark.usefixtures("_seed_type_projets_taxonomy")
class TestProjectCategoryOrdering:
    def test_categories_sorted_by_seq_not_alphabetically(self) -> None:
        """The canonical business order Erick set in the admin —
        Journalisme(10) → Communication(20) → Innovation(30) — must
        reach the form unchanged. A regression that re-sorts by name
        would yield Communication → Innovation → Journalisme."""
        choices = get_project_category_choices()

        # First entry is always the blank placeholder ; the rest is
        # the seq-ordered names.
        assert choices[0] == ("", "— Choisissez un type —")
        names_in_order = [label for _value, label in choices[1:]]

        # Pin the explicit order, not just « not alphabetical » — a
        # future refactor that swaps seq for created_at or similar
        # would silently shift the order.
        assert names_in_order == ["Journalisme", "Communication", "Innovation"]

    def test_first_category_is_journalisme(self) -> None:
        """Erick's emphasis : « Comme la plateforme est centrée sur
        le journalisme, il convient de rétablir le bon ordre ». Pin
        the first-category contract independently of the full
        ordering, so a future addition (e.g. a new « Cinéma »
        category inserted with seq=5) breaks loudly."""
        choices = get_project_category_choices()
        first_real_choice = choices[1]
        assert first_real_choice[1] == "Journalisme"
