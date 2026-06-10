# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Integration tests for app.modules.kyc.ontology_loader.

The a_unit tests for the taxonomy SERVICE layer
(`tests/a_unit/services/test_taxonomies.py`) already exercise
`get_taxonomy` / `get_full_taxonomy` / `get_taxonomy_dual_select` as
pure DB helpers. THIS file lives at the b_integration tier because it
drives the KYC ontology loader — the thin caching wrapper that the KYC
form layer actually calls — against the SAME real SQLAlchemy session.

What we cover here that a_unit cannot:

- The `ONTOLOGY_MAP` field-type -> ontology-name routing in
  `get_choices`, against real DB rows seeded via `TaxonomyEntry`.
- The `ONTOLOGY_DB_LIST` branch of `get_ontology_content`, which calls
  `get_full_taxonomy` and returns a flat `[(value, name), ...]` list
  ordered by `seq`.
- The default `get_taxonomy_dual_select` branch for taxonomies NOT in
  `ONTOLOGY_DB_LIST` (the `{"field1": ..., "field2": ...}` shape).
- The `cachetools.TTLCache` attached to `get_ontology_content`: we must
  invalidate it between tests (the cache is process-global and would
  otherwise leak rows across savepoint-rolled-back transactions).

No mocks, no monkeypatch, no MagicMock — per CLAUDE.md.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from app.modules.kyc.ontology_loader import (
    ONTOLOGY_DB_LIST,
    ONTOLOGY_MAP,
    get_choices,
    get_ontology_content,
)
from app.services.taxonomies import TaxonomyEntry

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


@pytest.fixture(autouse=True)
def _clear_ontology_cache() -> None:
    """Clear the TTLCache on `get_ontology_content` before each test.

    `@cached(cache=TTLCache(...))` from cachetools attaches the cache
    object as `func.cache`. Because tests run inside savepoints that
    roll back, a cached return from a previous test would silently mask
    the fact that the current test's DB rows aren't being read.
    """
    get_ontology_content.cache.clear()


def _seed(
    db_session: Session,
    taxonomy_name: str,
    rows: list[tuple[str, str, str, int]],
) -> None:
    """Insert (name, category, value, seq) rows for `taxonomy_name`."""
    for name, category, value, seq in rows:
        db_session.add(
            TaxonomyEntry(
                taxonomy_name=taxonomy_name,
                name=name,
                category=category,
                value=value,
                seq=seq,
            )
        )
    db_session.flush()


class TestGetOntologyContentDBList:
    """`get_ontology_content` -> `get_full_taxonomy` for ONTOLOGY_DB_LIST."""

    def test_empty_taxonomy_returns_empty_list(self, db_session: Session) -> None:
        # "civilite" is in ONTOLOGY_DB_LIST; no rows yet => empty list.
        assert "civilite" in ONTOLOGY_DB_LIST
        assert get_ontology_content("civilite") == []

    def test_returns_value_name_tuples_ordered_by_seq(
        self, db_session: Session
    ) -> None:
        _seed(
            db_session,
            "civilite",
            [
                ("Madame", "", "mme", 20),
                ("Monsieur", "", "m", 10),
                ("Autre", "", "x", 30),
            ],
        )

        result = get_ontology_content("civilite")

        # Flat list of (value, name) ordered by seq, NOT by name.
        assert result == [
            ("m", "Monsieur"),
            ("mme", "Madame"),
            ("x", "Autre"),
        ]

    @pytest.mark.parametrize(
        "ontology_name",
        ["langue", "media_type", "type_contenu", "mode_remuneration"],
    )
    def test_db_list_branch_for_known_ontologies(
        self, db_session: Session, ontology_name: str
    ) -> None:
        # Any ontology in ONTOLOGY_DB_LIST goes through the flat-list branch.
        assert ontology_name in ONTOLOGY_DB_LIST
        _seed(
            db_session,
            ontology_name,
            [("Alpha", "", "a", 1), ("Beta", "", "b", 2)],
        )
        result = get_ontology_content(ontology_name)
        assert result == [("a", "Alpha"), ("b", "Beta")]


class TestGetOntologyContentDualSelect:
    """Ontologies NOT in ONTOLOGY_DB_LIST take the dual-select branch."""

    def test_empty_taxonomy_returns_empty_dual_select(
        self, db_session: Session
    ) -> None:
        # `secteur_detaille` is referenced by ONTOLOGY_MAP but NOT in
        # ONTOLOGY_DB_LIST => dual-select shape.
        assert "secteur_detaille" not in ONTOLOGY_DB_LIST
        result = get_ontology_content("secteur_detaille")
        assert result == {"field1": [], "field2": {}}

    def test_groups_entries_by_category(self, db_session: Session) -> None:
        _seed(
            db_session,
            "secteur_detaille",
            [
                ("Banque", "Finance", "bank", 1),
                ("Assurance", "Finance", "ins", 2),
                ("Pharma", "Santé", "pharma", 3),
            ],
        )

        result = get_ontology_content("secteur_detaille")

        assert result["field1"] == [("Finance", "Finance"), ("Santé", "Santé")]
        assert result["field2"] == {
            "Finance": [["bank", "Banque"], ["ins", "Assurance"]],
            "Santé": [["pharma", "Pharma"]],
        }


class TestGetChoicesRouting:
    """`get_choices(field_type)` routes via ONTOLOGY_MAP, then delegates."""

    def test_unknown_field_type_in_map_raises(self, db_session: Session) -> None:
        # Field types not in ONTOLOGY_MAP fall through to a hard-coded
        # `choices_map` of four organisation-name helpers. Anything else
        # raises KeyError (documented behavior).
        with pytest.raises(KeyError):
            get_choices("definitely_not_a_field_type")

    def test_db_list_field_returns_flat_list(self, db_session: Session) -> None:
        # `list_civilite` -> `civilite` (in ONTOLOGY_DB_LIST) -> flat list.
        assert ONTOLOGY_MAP["list_civilite"] == "civilite"
        _seed(
            db_session,
            "civilite",
            [("Monsieur", "", "m", 10), ("Madame", "", "mme", 20)],
        )
        assert get_choices("list_civilite") == [
            ("m", "Monsieur"),
            ("mme", "Madame"),
        ]

    def test_dual_select_field_returns_dict(self, db_session: Session) -> None:
        # `multidual_secteurs_detail` -> `secteur_detaille` (NOT in
        # ONTOLOGY_DB_LIST) -> dual-select dict.
        assert ONTOLOGY_MAP["multidual_secteurs_detail"] == "secteur_detaille"
        _seed(
            db_session,
            "secteur_detaille",
            [("Banque", "Finance", "bank", 1)],
        )
        result = get_choices("multidual_secteurs_detail")
        assert isinstance(result, dict)
        assert result["field1"] == [("Finance", "Finance")]
        assert result["field2"] == {"Finance": [["bank", "Banque"]]}


class TestGetOntologyContentCacheInvalidation:
    """The TTLCache must be cleared to observe fresh DB state."""

    def test_cache_returns_stale_result_without_clear(
        self, db_session: Session
    ) -> None:
        # First call: empty DB -> empty list, cached.
        assert get_ontology_content("langue") == []

        # Seed new rows.
        _seed(db_session, "langue", [("Français", "", "fr", 1)])

        # WITHOUT clearing the cache, the loader returns the cached empty
        # list — this is the documented behavior of `@cached`.
        assert get_ontology_content("langue") == []

    def test_cache_clear_exposes_fresh_db_state(self, db_session: Session) -> None:
        # Same scenario, but invalidate the cache after seeding.
        assert get_ontology_content("langue") == []
        _seed(db_session, "langue", [("Français", "", "fr", 1)])

        get_ontology_content.cache.clear()

        assert get_ontology_content("langue") == [("fr", "Français")]
