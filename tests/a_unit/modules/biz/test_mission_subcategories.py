# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Unit tests for `_build_mission_subcategories`.

This pure helper lives in `app.modules.biz.views.missions` and powers
the per-request sub-category dict rendered in the publish-mission
form. The split between the pure builder and the I/O shell that
fetches the `genres` taxonomy lets us exercise the shape of the
dict — which is the part that actually matters to the form — without
patching anything.

Pinning the builder catches three classes of regression :
1. The hardcoded Communication / Innovation lists silently
   disappearing or losing canonical entries during a refactor.
2. The journalism slot leaking a non-list (e.g. tuple, set) which
   would break WTForms `SelectField.choices` consumers.
3. The dict losing the JOURNALISME key when the taxonomy returns an
   empty iterable — a misconfigured environment must still render
   the other two categories.

The 3-line I/O shell `get_mission_subcategories()` (try/except
around `get_taxonomy("genres")`) is left to integration coverage.
"""

from __future__ import annotations

import pytest

from app.modules.biz.models import MissionCategory
from app.modules.biz.views.missions import _build_mission_subcategories


class TestBuildMissionSubcategoriesShape:
    """The dict shape is the contract the publish form depends on."""

    def test_returns_three_categories(self):
        """All three top-level categories must be present, keyed by
        the canonical lowercase StrEnum value used by the form."""
        result = _build_mission_subcategories([])
        assert set(result.keys()) == {
            MissionCategory.JOURNALISME.value,
            MissionCategory.COMMUNICATION.value,
            MissionCategory.INNOVATION.value,
        }

    def test_three_categories_present_even_with_populated_journalism(self):
        """A non-empty journalism list doesn't change the key set."""
        result = _build_mission_subcategories(["Portrait", "Brève"])
        assert set(result.keys()) == {
            MissionCategory.JOURNALISME.value,
            MissionCategory.COMMUNICATION.value,
            MissionCategory.INNOVATION.value,
        }

    def test_all_values_are_lists(self):
        """WTForms `SelectField.choices` requires lists ; pin the type
        so a future refactor doesn't quietly switch to tuples."""
        result = _build_mission_subcategories(["A", "B"])
        for value in result.values():
            assert isinstance(value, list)


class TestBuildMissionSubcategoriesJournalism:
    """The journalism slot is the only runtime-sourced category."""

    def test_empty_journalism_list_yields_empty_slot(self):
        """The empty-list fallback that protects misconfigured envs
        must produce an empty journalism list, not a missing key."""
        result = _build_mission_subcategories([])
        assert result[MissionCategory.JOURNALISME.value] == []

    def test_journalism_entries_preserved_in_order(self):
        """The form renders the dropdown in the order supplied by the
        taxonomy ; pin the ordering so a refactor doesn't quietly
        sort or shuffle."""
        entries = ["Portrait", "Enquête", "Brève"]
        result = _build_mission_subcategories(entries)
        assert result[MissionCategory.JOURNALISME.value] == [
            "Portrait",
            "Enquête",
            "Brève",
        ]

    def test_journalism_slot_is_a_fresh_list(self):
        """The builder materialises the iterable into a *new* list, so
        callers mutating the returned dict can't reach back into the
        cached taxonomy result."""
        entries = ["Portrait", "Brève"]
        result = _build_mission_subcategories(entries)
        result[MissionCategory.JOURNALISME.value].append("Mutated")
        assert entries == ["Portrait", "Brève"]

    def test_accepts_arbitrary_iterable(self):
        """The signature is `Iterable[str]` ; a generator must work
        just as well as a list — the I/O shell currently wraps
        `get_taxonomy(...)` in `list(...)` but the builder should not
        depend on that."""

        def gen():
            yield "Portrait"
            yield "Brève"

        result = _build_mission_subcategories(gen())
        assert result[MissionCategory.JOURNALISME.value] == [
            "Portrait",
            "Brève",
        ]


class TestBuildMissionSubcategoriesHardcodedCategories:
    """Communication / Innovation lists were specced by Erick and
    are not (yet) admin-editable. Sample canonical entries so an
    accidental deletion is caught at unit-test time."""

    @pytest.mark.parametrize(
        "expected_entry",
        [
            "Communiqué de presse",
            "Conférence de presse / Événement",
            "Campagne RP",
            "Réseaux sociaux",
            "Stratégie / Conseil",
        ],
    )
    def test_communication_canonical_entries_present(self, expected_entry):
        result = _build_mission_subcategories([])
        assert expected_entry in result[MissionCategory.COMMUNICATION.value]

    @pytest.mark.parametrize(
        "expected_entry",
        [
            "Outil IA",
            "Newsletter / Plateforme",
            "Format vidéo / podcast",
            "Recherche / Étude",
            "Outil de gestion éditoriale",
        ],
    )
    def test_innovation_canonical_entries_present(self, expected_entry):
        result = _build_mission_subcategories([])
        assert expected_entry in result[MissionCategory.INNOVATION.value]

    def test_hardcoded_lists_survive_empty_journalism(self):
        """Even when the journalism slot is empty (DB failure / unset
        ontology) the other two categories must still render."""
        result = _build_mission_subcategories([])
        assert result[MissionCategory.COMMUNICATION.value]
        assert result[MissionCategory.INNOVATION.value]

    def test_hardcoded_lists_unchanged_by_journalism_input(self):
        """The journalism input must not bleed into the other two
        slots (e.g. via an accidental dict-merge inversion)."""
        result = _build_mission_subcategories(["Portrait", "Brève"])
        comm = result[MissionCategory.COMMUNICATION.value]
        innov = result[MissionCategory.INNOVATION.value]
        assert "Portrait" not in comm
        assert "Portrait" not in innov
        assert "Brève" not in comm
        assert "Brève" not in innov
