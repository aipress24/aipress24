# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Unit tests for the pure helpers behind the project-form selects in
`app.modules.biz.views.projects`.

The two `get_project_*` entry-points wrap a try/except around
`get_taxonomy(...)` and delegate to two pure builders :

- `_build_category_choices(rows)` — assembles the « blank-then-rows »
  select tuple list, with the hardcoded triple as fallback when the
  ontology is empty.
- `_build_subtypes_for_taxonomies(loader, taxonomies)` — fans the
  loader over the per-category taxonomy mapping, degrading any failing
  branch to an empty list.

These tests pin the contracts so a future change to the fallback set
or to the empty-degradation policy is caught. The loader is an actual
callable function (DI via real-fake), so there's no patching.
"""

from __future__ import annotations

from collections.abc import Iterable

import pytest

from app.modules.biz.views.projects import (
    _PROJECT_CATEGORY_VALUES,
    _PROJECT_SUBTYPE_TAXONOMIES,
    _build_category_choices,
    _build_subtypes_for_taxonomies,
    get_project_category_choices,
    get_project_subtypes,
)

# ---------------------------------------------------------------------
# _build_category_choices : the pure « blank + rows | fallback » join
# ---------------------------------------------------------------------


class TestBuildCategoryChoices:
    def test_empty_taxonomy_falls_back_to_hardcoded_values(self):
        """When the ontology returns nothing, callers must still see
        the journalism / communication / innovation triple — the form
        cannot render an empty select."""
        result = _build_category_choices([])

        assert result[0] == ("", "— Choisissez un type —")
        assert result[1:] == list(_PROJECT_CATEGORY_VALUES)
        # Exactly the blank + the fallback triple, nothing more.
        assert len(result) == 1 + len(_PROJECT_CATEGORY_VALUES)

    def test_populated_taxonomy_uses_rows_as_value_and_label(self):
        """The `type_projets` names are display-ready French labels,
        so each row goes in twice : once as the option `value`, once
        as the visible `label`."""
        result = _build_category_choices(["Journalisme", "Communication"])

        assert result == [
            ("", "— Choisissez un type —"),
            ("Journalisme", "Journalisme"),
            ("Communication", "Communication"),
        ]

    def test_blank_prefix_is_always_first(self):
        """The blank-prefix anchors the select as « optional ». A
        regression that swaps the order would silently flip the form
        into « pre-selected first row »."""
        empty_first = _build_category_choices([])
        populated_first = _build_category_choices(["X"])

        assert empty_first[0][0] == ""
        assert populated_first[0][0] == ""

    @pytest.mark.parametrize(
        "rows",
        [
            ["A"],
            ["A", "B"],
            ["A", "B", "C", "D"],
        ],
    )
    def test_populated_taxonomy_preserves_order(self, rows: list[str]):
        """The taxonomy admin defines a display order — preserve it,
        don't sort alphabetically."""
        result = _build_category_choices(rows)
        assert [v for v, _ in result[1:]] == rows

    def test_accepts_iterable_not_just_list(self):
        """The shell calls `_build_category_choices(list(get_taxonomy(...)))`
        today, but the pure builder is contracted on `Iterable[str]` so
        single-pass generators must work too."""

        def gen():
            yield "Alpha"
            yield "Beta"

        result = _build_category_choices(gen())

        assert result == [
            ("", "— Choisissez un type —"),
            ("Alpha", "Alpha"),
            ("Beta", "Beta"),
        ]

    def test_returns_fresh_list(self):
        """Two calls must yield independent lists. Otherwise a caller
        mutating the result (e.g. WTForms reassigning `choices`) would
        bleed into the next request."""
        first = _build_category_choices([])
        second = _build_category_choices([])

        assert first == second
        assert first is not second


# ---------------------------------------------------------------------
# _build_subtypes_for_taxonomies : loader fan-out with safe fallback
# ---------------------------------------------------------------------


class TestBuildSubtypesForTaxonomies:
    def test_loader_is_called_per_taxonomy_with_correct_name(self):
        """Each category's taxonomy name is looked up exactly once."""
        seen: list[str] = []

        def fake_loader(name: str) -> Iterable[str]:
            seen.append(name)
            return []

        _build_subtypes_for_taxonomies(fake_loader, {"a": "tax_a", "b": "tax_b"})

        assert seen == ["tax_a", "tax_b"]

    def test_returns_per_category_rows_from_loader(self):
        """Pin the canonical happy path : the loader's rows land
        under the matching category key, in order."""
        canned = {
            "tax_journ": ["Reportage", "Interview"],
            "tax_com": ["Brochure"],
            "tax_inno": ["Lab"],
        }

        def fake_loader(name: str) -> Iterable[str]:
            return canned[name]

        result = _build_subtypes_for_taxonomies(
            fake_loader,
            {
                "journalisme": "tax_journ",
                "communication": "tax_com",
                "innovation": "tax_inno",
            },
        )

        assert result == {
            "journalisme": ["Reportage", "Interview"],
            "communication": ["Brochure"],
            "innovation": ["Lab"],
        }

    def test_loader_failure_degrades_to_empty_list_per_branch(self):
        """A failing loader for one taxonomy must not poison the
        others. The branch degrades to an empty list — template
        renders an empty select, the rest of the cascade still works."""

        msg = "typesense down"

        def fake_loader(name: str) -> Iterable[str]:
            if name == "tax_b":
                raise RuntimeError(msg)
            return ["row-" + name]

        result = _build_subtypes_for_taxonomies(
            fake_loader, {"a": "tax_a", "b": "tax_b", "c": "tax_c"}
        )

        assert result == {
            "a": ["row-tax_a"],
            "b": [],
            "c": ["row-tax_c"],
        }

    def test_keys_match_input_taxonomies(self):
        """Cross-check : every key in the result corresponds to a
        category from the input mapping, and vice-versa."""

        def fake_loader(name: str) -> Iterable[str]:
            return []

        taxonomies = {"journalisme": "tj", "communication": "tc"}
        result = _build_subtypes_for_taxonomies(fake_loader, taxonomies)

        assert set(result.keys()) == set(taxonomies.keys())

    def test_empty_taxonomy_mapping_returns_empty_dict(self):
        """No categories in → no categories out. The loader is never
        called."""
        calls: list[str] = []

        def fake_loader(name: str) -> Iterable[str]:
            calls.append(name)
            return []

        result = _build_subtypes_for_taxonomies(fake_loader, {})

        assert result == {}
        assert calls == []

    def test_loader_iterable_is_materialised_to_list(self):
        """The shell stores the result in a dict that may be cached or
        iterated more than once. A single-pass generator from the
        loader must be turned into a fully-realised list."""

        def fake_loader(name: str) -> Iterable[str]:
            def gen():
                yield "first"
                yield "second"

            return gen()

        result = _build_subtypes_for_taxonomies(fake_loader, {"k": "t"})

        assert isinstance(result["k"], list)
        assert result["k"] == ["first", "second"]


# ---------------------------------------------------------------------
# Public entry points : light smoke tests via the production loader
# ---------------------------------------------------------------------


class TestGetProjectCategoryChoices:
    def test_always_starts_with_blank_entry(self):
        """Whatever the ontology state, the select always reads as
        optional. Anchors the public contract."""
        result = get_project_category_choices()

        assert result[0] == ("", "— Choisissez un type —")
        assert len(result) >= 1 + len(_PROJECT_CATEGORY_VALUES)


class TestGetProjectSubtypes:
    def test_returns_one_entry_per_known_category(self):
        """The public entry point keys the dict on the project
        category strings. The cascade template would break if a key
        went missing."""
        result = get_project_subtypes()

        assert set(result.keys()) == set(_PROJECT_SUBTYPE_TAXONOMIES.keys())

    def test_values_are_always_lists(self):
        """Even when a branch fails (empty fallback), the value must
        be a list — `.length` checks in the Alpine cascade assume so."""
        result = get_project_subtypes()

        for value in result.values():
            assert isinstance(value, list)
