# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Unit tests for the « base infrastructure » of expert filter selectors.

This file pins the shared building blocks every concrete selector
inherits from in
`app.modules.wip.services.newsroom.expert_selectors`:

  - `FilterOption`           — display row dataclass
  - `_normalize`             — diacritic-stripping sort key
  - `BaseSelector`           — flat selector base class
  - `DualSelector`           — two-level (parent / child) cascade base

WHY this file exists
====================

The per-selector test files (`test_expert_selectors_metier.py`,
`test_expert_selectors_general.py`, …) cover the « this concrete
selector reads attribute X » contract. That coverage is meaningless
if the underlying `BaseSelector._make_options`, `_count_by_value`,
`filter_experts` infrastructure regresses: a bug in `_make_options`
would propagate to every selector at once and look like a uniform
display drift.

This file therefore exercises that shared core directly via two trivial
in-file subclasses:

  - `_FlatSelector(BaseSelector)` — flat, reads `expert.tags`
  - `_CascadeSelector(DualSelector)` — cascade, reads `expert.detail`

Both wear `taxonomy_name = "fake"` so the DI'd `taxonomy_loader` /
`dual_taxonomy_loader` parameters get exercised end-to-end without
booting Flask, the KYC ontology, or the DB.

We use stand-in `User` / `Profile` duck-typed classes — the base only
calls `_expert_values` on us, never anything ORM-shaped.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any

import pytest

from app.modules.wip.services.newsroom.expert_selectors import (
    BaseSelector,
    DualSelector,
    FilterOption,
    _normalize,
)

# ----------------------------------------------------------------
# Stand-in stubs : duck-typed User / Profile + tiny subclasses of
# BaseSelector and DualSelector. These exist purely to give the
# abstract base classes something concrete to dispatch against.
# ----------------------------------------------------------------


@dataclass
class _StandInProfile:
    """Minimal duck-typed `KYCProfile`. The base classes never read it
    directly — our `_expert_values` overrides do."""

    tags: list[str] = field(default_factory=list)
    detail: list[str] = field(default_factory=list)


@dataclass
class _StandInUser:
    """Minimal duck-typed `User` exposing a `_StandInProfile`."""

    profile: _StandInProfile = field(default_factory=_StandInProfile)


class _FlatSelector(BaseSelector):
    """Trivial flat selector reading `expert.profile.tags`.

    `taxonomy_name = "fake"` so `get_values()` triggers the injected
    `taxonomy_loader` — we want that branch exercised without an
    actual taxonomies service in scope.
    """

    id = "tag"
    label = "Tag"
    taxonomy_name = "fake"

    def _expert_values(self, expert: _StandInUser) -> Iterable[str]:  # type: ignore[override]
        return expert.profile.tags


class _CascadeSelector(DualSelector):
    """Trivial cascade selector reading `expert.profile.detail`."""

    id = "detail"
    label = "Detail"
    parent_id = "detail_parent"
    parent_label = "Parent"
    taxonomy_name = "fake_dual"

    def _expert_values(self, expert: _StandInUser) -> Iterable[str]:  # type: ignore[override]
        return expert.profile.detail


# ----------------------------------------------------------------
# Pattern B stand-in loaders (in-memory taxonomies).
# ----------------------------------------------------------------


def _make_loader(table: dict[str, list[str]]) -> Any:
    """Build a stand-in `TaxonomyLoader` returning canned data."""

    def loader(name: str) -> list[str]:
        return list(table.get(name, []))

    return loader


def _make_dual_loader(table: dict[str, dict[str, Any]]) -> Any:
    """Build a stand-in `DualTaxonomyLoader` returning canned dual-select
    data. Shape matches `get_taxonomy_dual_select`:

        { "field1": [(cat, cat), ...],
          "field2": { cat: [[value, label], ...], ... } }
    """

    def loader(name: str) -> dict[str, Any]:
        return table.get(name, {"field1": [], "field2": {}})

    return loader


# ================================================================
# Tests
# ================================================================


class TestFilterOption:
    """`FilterOption` is a frozen dataclass with default ordering by
    `id`. The dropdown rendering pipeline relies on this stability —
    pin the basics."""

    def test_filter_option_holds_id_label_and_selected(self) -> None:
        """The three fields the template reads round-trip through the
        dataclass without surprise."""
        opt = FilterOption(id="fr", label="France (3)", selected="selected")
        assert opt.id == "fr"
        assert opt.label == "France (3)"
        assert opt.selected == "selected"

    def test_filter_option_selected_defaults_to_empty_string(self) -> None:
        """Empty-string default keeps Jinja template
        `<option {{ opt.selected }}>` valid HTML even for un-selected
        rows."""
        opt = FilterOption(id="fr", label="France (3)")
        assert opt.selected == ""

    def test_filter_option_is_frozen(self) -> None:
        """`frozen=True` so the option list can be safely cached across
        renders without an inadvertent mutation poisoning later
        requests."""
        opt = FilterOption(id="fr", label="France (3)")
        with pytest.raises(AttributeError):
            opt.label = "tampered"  # type: ignore[misc]

    def test_filter_option_orders_by_id_by_default(self) -> None:
        """Dataclass `order=True` sorts by `id` first. `_make_options`
        overrides this with a diacritic-stripped label sort, but the
        default order is the safety-net for any code path that drops
        the explicit sort."""
        a = FilterOption(id="a", label="zzz")
        z = FilterOption(id="z", label="aaa")
        assert sorted([z, a]) == [a, z]


class TestNormalize:
    """`_normalize` is the sort key for the dropdown — it MUST be
    case-insensitive AND diacritic-insensitive. Otherwise « Élève »
    sorts after « Zéro », which is exactly the visual bug that drove
    this helper's existence."""

    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            # Lowercasing
            ("FOO", "foo"),
            ("Foo", "foo"),
            # French diacritics that MUST collapse: é è ê ë → e
            ("école", "ecole"),
            ("élève", "eleve"),
            ("ÉCOLE", "ecole"),
            ("être", "etre"),
            # à â ä → a
            ("château", "chateau"),
            # ç → c
            ("garçon", "garcon"),
            ("Français", "francais"),
            # ô ö → o
            ("hôtel", "hotel"),
            # ï î → i
            ("naïf", "naif"),
            # ù û ü → u
            ("où", "ou"),
            # Already-clean strings pass through unchanged (lowercase)
            ("paris", "paris"),
            # Empty string
            ("", ""),
        ],
    )
    def test_normalize_lowers_and_strips_diacritics(
        self, raw: str, expected: str
    ) -> None:
        assert _normalize(raw) == expected

    def test_normalize_makes_accent_variants_compare_equal(self) -> None:
        """`Élève` and `eleve` must sort to the same position so that
        a user typing without accents finds the accented entry. This
        is the regression scenario the helper was introduced to fix."""
        assert _normalize("Élève") == _normalize("eleve")

    def test_normalize_orders_accented_french_alphabetically(self) -> None:
        """Real sort: a list of common French nouns sorts the way a
        French reader would expect — `école` before `étoile`, both
        before « voiture », not after « zoo »."""
        words = ["zoo", "étoile", "voiture", "école"]
        sorted_words = sorted(words, key=_normalize)
        assert sorted_words == ["école", "étoile", "voiture", "zoo"]


class TestBaseSelectorConstructor:
    """`BaseSelector.__init__` parses the form state into a string-set
    `self.values`. Every concrete selector relies on this — a bug here
    would silently drop the user's selection on the next HTMX
    re-render."""

    def test_empty_state_yields_empty_value_set(self) -> None:
        sel = _FlatSelector({}, [])
        assert sel.values == set()

    def test_list_state_becomes_string_set(self) -> None:
        sel = _FlatSelector({"tag": ["a", "b"]}, [])
        assert sel.values == {"a", "b"}

    def test_scalar_state_is_wrapped_into_a_singleton_set(self) -> None:
        """If the form posts a single value (no `[]` suffix), the
        selector still surfaces a 1-element set so `_make_options`'s
        « is the value currently selected? » lookup works."""
        sel = _FlatSelector({"tag": "solo"}, [])
        assert sel.values == {"solo"}

    def test_int_values_are_coerced_to_strings(self) -> None:
        """`FilterState` allows `list[int]` for the `selected_experts`
        key — but each individual selector keys by string. Coercion is
        the contract."""
        sel = _FlatSelector({"tag": [1, 2]}, [])
        assert sel.values == {"1", "2"}

    def test_unrelated_state_keys_are_ignored(self) -> None:
        """A selector for `tag` doesn't read `other_id`'s value."""
        sel = _FlatSelector({"other_id": ["x"]}, [])
        assert sel.values == set()


class TestBaseSelectorCountByValue:
    """`_count_by_value` is the headcount badge feeding the `(N)` label
    suffix. It's a `cached_property` so the lazy-iteration matters."""

    def test_count_by_value_counts_each_expert_value(self) -> None:
        e1 = _StandInUser(profile=_StandInProfile(tags=["a", "b"]))
        e2 = _StandInUser(profile=_StandInProfile(tags=["a"]))
        sel = _FlatSelector({}, [e1, e2])
        assert sel._count_by_value == {"a": 2, "b": 1}

    def test_count_by_value_empty_pool_yields_empty_dict(self) -> None:
        sel = _FlatSelector({}, [])
        assert sel._count_by_value == {}


class TestBaseSelectorMakeOptions:
    """`_make_options` is the heart of the « options the user sees »
    pipeline — it drops zero-count values, preserves selected chips,
    appends `(N)` badges, and sorts diacritic-insensitively."""

    def test_zero_count_unselected_values_are_dropped(self) -> None:
        """Annie's explicit rule: a value with no matching expert is
        noise — don't surface it."""
        experts = [_StandInUser(profile=_StandInProfile(tags=["a"]))]
        sel = _FlatSelector({}, experts)
        options = sel._make_options(["a", "ghost"])
        assert [o.id for o in options] == ["a"]

    def test_zero_count_selected_value_is_preserved(self) -> None:
        """Currently-selected chips must NEVER disappear mid-edit —
        even if no expert matches, the user's choice stays visible
        across HTMX re-renders. Bug #0150's chip-preservation rule."""
        experts = [_StandInUser(profile=_StandInProfile(tags=["a"]))]
        sel = _FlatSelector({"tag": ["ghost"]}, experts)
        options = sel._make_options(["a", "ghost"])
        assert [o.id for o in options] == ["a", "ghost"]
        ghost = next(o for o in options if o.id == "ghost")
        assert ghost.selected == "selected"
        assert ghost.label == "ghost (0)"

    def test_label_carries_count_badge(self) -> None:
        e1 = _StandInUser(profile=_StandInProfile(tags=["a"]))
        e2 = _StandInUser(profile=_StandInProfile(tags=["a"]))
        sel = _FlatSelector({}, [e1, e2])
        options = sel._make_options(["a"])
        assert options[0].label == "a (2)"

    def test_options_are_sorted_diacritic_insensitively(self) -> None:
        """`école` MUST sort before `zoo`, not after. This is the
        rendering bug that drove `_normalize` into existence."""
        experts = [
            _StandInUser(profile=_StandInProfile(tags=["zoo", "école", "étoile"])),
        ]
        sel = _FlatSelector({}, experts)
        options = sel._make_options(["zoo", "école", "étoile"])
        assert [o.id for o in options] == ["école", "étoile", "zoo"]

    def test_duplicate_input_values_are_deduplicated(self) -> None:
        """`_make_options` tolerates duplicate inputs (the union of
        taxonomy + expert values can overlap) — each value appears once."""
        experts = [_StandInUser(profile=_StandInProfile(tags=["a"]))]
        sel = _FlatSelector({}, experts)
        options = sel._make_options(["a", "a", "a"])
        assert [o.id for o in options] == ["a"]

    def test_empty_string_values_are_skipped(self) -> None:
        """A blank-string value isn't a real chip — skip silently so
        a stray empty taxonomy row doesn't render an empty `<option>`."""
        experts = [_StandInUser(profile=_StandInProfile(tags=["", "a"]))]
        sel = _FlatSelector({}, experts)
        options = sel._make_options(["", "a"])
        assert [o.id for o in options] == ["a"]


class TestBaseSelectorGetValues:
    """`get_values()` is the union (taxonomy ∪ expert-held ∪ user-
    selected). DI'd taxonomy loader makes this testable without
    Flask / DB."""

    def test_get_values_unions_taxonomy_experts_and_selected(self) -> None:
        loader = _make_loader({"fake": ["from_taxo"]})
        experts = [_StandInUser(profile=_StandInProfile(tags=["from_expert"]))]
        sel = _FlatSelector({"tag": ["from_selected"]}, experts, taxonomy_loader=loader)
        assert sel.get_values() == {
            "from_taxo",
            "from_expert",
            "from_selected",
        }

    def test_get_values_with_no_taxonomy_name_skips_loader(self) -> None:
        """When `taxonomy_name = None`, the loader is never invoked —
        a recording stand-in proves it stays untouched."""
        calls: list[str] = []

        def recording_loader(name: str) -> list[str]:
            calls.append(name)
            return []

        class _NoTaxonomy(_FlatSelector):
            taxonomy_name = None

        sel = _NoTaxonomy({}, [], taxonomy_loader=recording_loader)
        sel.get_values()
        assert calls == []


class TestBaseSelectorFilterExperts:
    """`filter_experts` is the default intersection-based predicate.
    Empty criteria = identity (no filter); non-empty = keep experts
    whose values touch the criteria."""

    def test_empty_criteria_returns_all_experts(self) -> None:
        e1 = _StandInUser(profile=_StandInProfile(tags=["a"]))
        e2 = _StandInUser(profile=_StandInProfile(tags=["b"]))
        sel = _FlatSelector({}, [e1, e2])
        assert sel.filter_experts(set(), [e1, e2]) == [e1, e2]

    def test_filter_keeps_experts_whose_values_intersect(self) -> None:
        match = _StandInUser(profile=_StandInProfile(tags=["a", "b"]))
        miss = _StandInUser(profile=_StandInProfile(tags=["c"]))
        sel = _FlatSelector({}, [match, miss])
        assert sel.filter_experts({"a"}, [match, miss]) == [match]


class TestBaseSelectorOptionsIntegration:
    """`.options` (the public property) composes `get_values()` and
    `_make_options()` — end-to-end happy path: taxonomy entries with
    matches surface, selected chips persist, output is sorted."""

    def test_options_property_yields_count_labelled_sorted_options(self) -> None:
        loader = _make_loader({"fake": ["alpha", "beta", "ghost"]})
        experts = [
            _StandInUser(profile=_StandInProfile(tags=["alpha", "beta"])),
            _StandInUser(profile=_StandInProfile(tags=["beta"])),
        ]
        sel = _FlatSelector({}, experts, taxonomy_loader=loader)
        options = sel.options
        # ghost has 0 matches and is not selected — must be dropped.
        labels = [o.label for o in options]
        ids = [o.id for o in options]
        assert ids == ["alpha", "beta"]
        assert labels == ["alpha (1)", "beta (2)"]


class TestDualSelectorWtformsShape:
    """`DualSelector` mimics a wtforms field so the existing
    `dual_select_multi.j2` template renders it directly. Pin the
    aliases that template depends on."""

    def test_name_returns_parent_id(self) -> None:
        sel = _CascadeSelector({}, [])
        assert sel.name == "detail_parent"

    def test_name2_returns_child_id(self) -> None:
        sel = _CascadeSelector({}, [])
        assert sel.name2 == "detail"

    def test_id2_and_label2_round_trip_to_child_id_and_label(self) -> None:
        sel = _CascadeSelector({}, [])
        assert sel.id2 == "detail"
        assert sel.label2 == "Detail"

    def test_flags_required_is_false(self) -> None:
        """The ciblage cascade is always optional; the wtforms-shaped
        `flags.required` flag must be False so the template doesn't
        render a `*` marker."""
        sel = _CascadeSelector({}, [])
        assert sel.flags.required is False

    def test_is_dual_is_true(self) -> None:
        """Template routing checks `selector.is_dual` to pick the
        cascade partial. Any cascade subclass MUST advertise True."""
        sel = _CascadeSelector({}, [])
        assert sel.is_dual is True


class TestDualSelectorGetData:
    """`get_data` / `get_data2` are the initial payloads the JS reads
    on first render."""

    def test_get_data_returns_selected_parent_values_as_strings(self) -> None:
        sel = _CascadeSelector({"detail_parent": ["Cat1", "Cat2"]}, [])
        assert sel.get_data() == ["Cat1", "Cat2"]

    def test_get_data_wraps_a_scalar_parent_in_a_list(self) -> None:
        """The state dict may contain a single string when the form
        posts only one parent value; the JS expects a list."""
        sel = _CascadeSelector({"detail_parent": "Solo"}, [])
        assert sel.get_data() == ["Solo"]

    def test_get_data_with_no_parent_state_is_empty(self) -> None:
        sel = _CascadeSelector({}, [])
        assert sel.get_data() == []

    def test_get_data2_returns_sorted_detail_values(self) -> None:
        """Detail values come back sorted so the rendered chips are
        deterministic across reloads (= friendlier diffs in
        screenshots and tests)."""
        sel = _CascadeSelector({"detail": ["zeta", "alpha"]}, [])
        assert sel.get_data2() == ["alpha", "zeta"]


class TestDualSelectorChoicesForJs:
    """`get_dual_tom_choices_for_js` is the cascade's main rendering
    payload. With the injected `dual_taxonomy_loader`, we can exercise
    the full « drop zero-count, preserve user selection, sum-up to
    parent counts » pipeline without touching the DB."""

    def _make_dual_table(self) -> dict[str, dict[str, Any]]:
        """Sample dual-taxonomy with two parents, two children each.

        Matches the shape `get_taxonomy_dual_select` produces, which
        `convert_dual_choices_js` re-shapes into the flat
        `field1` / `field2` lists `get_dual_tom_choices_for_js` reads.
        """
        return {
            "fake_dual": {
                "field1": [("Cat1", "Cat1"), ("Cat2", "Cat2")],
                "field2": {
                    "Cat1": [
                        ["Cat1 / Child1", "Cat1 / Child1"],
                        ["Cat1 / Child2", "Cat1 / Child2"],
                    ],
                    "Cat2": [
                        ["Cat2 / ChildA", "Cat2 / ChildA"],
                    ],
                },
            }
        }

    def test_children_with_no_match_are_dropped(self) -> None:
        loader = _make_dual_loader(self._make_dual_table())
        experts = [
            _StandInUser(profile=_StandInProfile(detail=["Cat1 / Child1"])),
        ]
        sel = _CascadeSelector({}, experts, dual_taxonomy_loader=loader)
        result = sel.get_dual_tom_choices_for_js()
        child_ids = [c["value"] for c in result["field2"]]
        assert "Cat1 / Child1" in child_ids
        # Child2 has 0 matches AND isn't user-selected → dropped.
        assert "Cat1 / Child2" not in child_ids
        # ChildA has 0 matches AND isn't user-selected → dropped.
        assert "Cat2 / ChildA" not in child_ids

    def test_parent_keeps_only_categories_with_surviving_children(self) -> None:
        loader = _make_dual_loader(self._make_dual_table())
        experts = [
            _StandInUser(profile=_StandInProfile(detail=["Cat1 / Child1"])),
        ]
        sel = _CascadeSelector({}, experts, dual_taxonomy_loader=loader)
        result = sel.get_dual_tom_choices_for_js()
        parent_ids = [p["value"] for p in result["field1"]]
        assert parent_ids == ["Cat1"]

    def test_parent_label_carries_summed_count_badge(self) -> None:
        loader = _make_dual_loader(self._make_dual_table())
        experts = [
            _StandInUser(profile=_StandInProfile(detail=["Cat1 / Child1"])),
            _StandInUser(profile=_StandInProfile(detail=["Cat1 / Child1"])),
        ]
        sel = _CascadeSelector({}, experts, dual_taxonomy_loader=loader)
        result = sel.get_dual_tom_choices_for_js()
        cat1 = next(p for p in result["field1"] if p["value"] == "Cat1")
        # Two experts matched Cat1 / Child1 → parent count 2.
        assert cat1["label"].endswith("(2)")

    def test_child_label_carries_count_badge(self) -> None:
        loader = _make_dual_loader(self._make_dual_table())
        experts = [
            _StandInUser(profile=_StandInProfile(detail=["Cat1 / Child1"])),
            _StandInUser(profile=_StandInProfile(detail=["Cat1 / Child1"])),
        ]
        sel = _CascadeSelector({}, experts, dual_taxonomy_loader=loader)
        result = sel.get_dual_tom_choices_for_js()
        child = next(c for c in result["field2"] if c["value"] == "Cat1 / Child1")
        assert child["label"].endswith("(2)")

    def test_selected_parent_with_no_surviving_child_is_preserved(self) -> None:
        """Annie's chip-preservation rule for the cascade : a parent
        the user explicitly picked stays in the dropdown even if 0
        children remain — otherwise the user's own chip would vanish
        on the next HTMX re-render."""
        loader = _make_dual_loader(self._make_dual_table())
        # No experts match anything but the user has clicked Cat2 as a
        # parent. Cat2's surviving children = [] → Cat2 must still
        # appear with a (0) badge.
        sel = _CascadeSelector(
            {"detail_parent": ["Cat2"]},
            [],
            dual_taxonomy_loader=loader,
        )
        result = sel.get_dual_tom_choices_for_js()
        cat2 = next((p for p in result["field1"] if p["value"] == "Cat2"), None)
        assert cat2 is not None
        assert cat2["label"].endswith("(0)")

    def test_selected_child_with_no_match_is_preserved(self) -> None:
        """Chip-preservation for the child level. Even if no expert
        in the candidate pool holds it, the user's own selection
        survives the next HTMX re-render."""
        loader = _make_dual_loader(self._make_dual_table())
        sel = _CascadeSelector(
            {"detail": ["Cat1 / Child2"]},
            [],
            dual_taxonomy_loader=loader,
        )
        result = sel.get_dual_tom_choices_for_js()
        child_ids = [c["value"] for c in result["field2"]]
        assert "Cat1 / Child2" in child_ids
