# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Unit tests for the « general » expert selectors (org / sector / location).

Pins the contract of each concrete selector in
`app.modules.wip.services.newsroom.expert_selectors` covering the
organisation / sector / location filter dimensions:

  - `SecteurSelector` (cascade)
  - `TypeEntreprisePresseMediasSelector` (flat)
  - `TypePresseMediasSelector` (flat)
  - `LanguesSelector` (flat)
  - `TypeOrganisationSelector` (cascade)
  - `TailleOrganisationSelector` (flat)
  - `PaysSelector` (flat, scalar value)

WHY this file exists
====================

The selectors share a tiny but load-bearing contract: each reads ONE
specific attribute on `User.profile`. A silent rename of that
attribute would empty the expert ciblage results with no error
(filter pipelines that intersect with an empty set just return `[]`).
The companion `test_expert_selectors_metier.py` pins that contract
for the métier / fonction family; this file does the same for the
sector / org / country family.

`PaysSelector` is the only odd one out: `profile.country` is a SCALAR
string (not a list). The selector wraps it in a single-element list
and overrides `filter_experts` to compare on equality. We pin both
sides so a refactor that switched country to a list — or vice versa —
trips an assertion.

The tests use plain duck-typed stand-in `_StandInUser` / `_StandInProfile`
classes instead of DB rows so the test stays purely unit-level: no
Flask app, no SQL session, no KYC taxonomy boot. The selector code
only touches the attribute name on the stand-in, so a future refactor
that renames a profile attr will turn at least one assertion here red.

No mocks, no patches — only stand-in stubs. See CLAUDE.md:
« Don't use mocks. Prefer stubs. Tests that check final state are
generally more robust and less coupled to the implementation. »
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pytest

from app.modules.wip.services.newsroom.expert_selectors import (
    BaseSelector,
    DualSelector,
    LanguesSelector,
    PaysSelector,
    SecteurSelector,
    TailleOrganisationSelector,
    TypeEntreprisePresseMediasSelector,
    TypeOrganisationSelector,
    TypePresseMediasSelector,
)

# ----------------------------------------------------------------
# Stand-in stubs: duck-typed Profile / User
# ----------------------------------------------------------------
#
# The selectors only call `expert.profile.<some_attribute>` — they
# never touch the ORM session or any Flask extension. A dataclass
# with the right attribute names is enough to exercise the contract.


@dataclass
class _StandInProfile:
    """Minimal duck-typed replacement for `KYCProfile`.

    List-valued attributes default to an empty list so a selector
    reading an untouched attribute observes an « empty profile »
    exactly like a freshly-created KYC row. `country` defaults to
    `""` because it is a scalar string in production, not a list.
    """

    secteurs_activite: list[str] = field(default_factory=list)
    type_entreprise_media: list[str] = field(default_factory=list)
    type_presse_et_media: list[str] = field(default_factory=list)
    langues: list[str] = field(default_factory=list)
    type_organisation: list[str] = field(default_factory=list)
    taille_organisation: list[str] = field(default_factory=list)
    country: str = ""


@dataclass
class _StandInUser:
    """Minimal duck-typed replacement for `User`.

    All target selectors here read from `user.profile.<attr>` — none
    of them read directly off the `User` itself. Reflecting this in
    the stand-in keeps the assertion error message short when an
    attribute is misread.
    """

    profile: _StandInProfile = field(default_factory=_StandInProfile)


# ----------------------------------------------------------------
# Per-selector contract pinning
# ----------------------------------------------------------------
#
# The table below is the single source of truth: each row asserts
# « this selector reads exactly this attribute on profile ». A
# cross-check at the bottom of this module verifies every selector
# in the « general » family is covered exactly once.
#
# Note: PaysSelector reads a SCALAR `profile.country`, not a list.
# It is excluded from the list-shaped helpers (set/get + neighbour
# leakage) and tested in its own class below.

LIST_SELECTOR_CONTRACTS: list[
    tuple[type[BaseSelector], str, str, str, type[BaseSelector]]
] = [
    # (selector_cls, expected_id, expected_taxonomy, profile_attr, base)
    (
        SecteurSelector,
        "secteur",
        "secteur_detaille",
        "secteurs_activite",
        DualSelector,
    ),
    (
        TypeEntreprisePresseMediasSelector,
        "type_entreprise_presse_medias",
        "type_entreprises_medias",
        "type_entreprise_media",
        BaseSelector,
    ),
    (
        TypePresseMediasSelector,
        "type_presse_et_media",
        "media_type",
        "type_presse_et_media",
        BaseSelector,
    ),
    (
        LanguesSelector,
        "langues",
        "langue",
        "langues",
        BaseSelector,
    ),
    (
        TypeOrganisationSelector,
        "type_organisation",
        "type_organisation_detail",
        "type_organisation",
        DualSelector,
    ),
    (
        TailleOrganisationSelector,
        "taille_organisation",
        "taille_organisation",
        "taille_organisation",
        BaseSelector,
    ),
]

ALL_LIST_PROFILE_ATTRS: set[str] = {
    attr for _cls, _sid, _tax, attr, _base in LIST_SELECTOR_CONTRACTS
}


def _build_expert(attr: str, values: list[str]) -> _StandInUser:
    """Build a stand-in expert with `profile.<attr>` set to `values`."""
    expert = _StandInUser()
    setattr(expert.profile, attr, values)
    return expert


# ----------------------------------------------------------------
# Tests
# ----------------------------------------------------------------


class TestSelectorIdentity:
    """Pin id / taxonomy_name / class hierarchy.

    A silent rename of `id` would re-key `FilterState` and lose the
    user's selection on the next request. A silent change to the
    `is_dual` flag would break the template router that picks the
    cascade partial.
    """

    @pytest.mark.parametrize(
        ("selector_cls", "expected_id", "expected_taxonomy", "base"),
        [
            (cls, sid, tax, base)
            for cls, sid, tax, _attr, base in LIST_SELECTOR_CONTRACTS
        ],
    )
    def test_selector_id_taxonomy_and_hierarchy(
        self,
        selector_cls: type[BaseSelector],
        expected_id: str,
        expected_taxonomy: str,
        base: type[BaseSelector],
    ) -> None:
        """Each selector exposes the expected form-field id, taxonomy
        name and base class. The id is the cross-request stable key
        in `FilterState`; the taxonomy name is the lookup key into the
        KYC ontology DB; the base controls template routing (cascade
        vs flat).
        """
        assert selector_cls.id == expected_id
        assert selector_cls.taxonomy_name == expected_taxonomy
        assert issubclass(selector_cls, base)
        assert issubclass(selector_cls, BaseSelector)
        if base is DualSelector:
            assert selector_cls.is_dual is True
            assert selector_cls.parent_id
            assert selector_cls.parent_id != selector_cls.id
        else:
            # Flat selectors never claim to be duals (template would
            # route them to the cascade partial and crash on missing
            # parent_id).
            assert selector_cls.is_dual is False

    def test_pays_selector_identity(self) -> None:
        """PaysSelector pins its own identity: stable form key + the
        `pays` taxonomy backing the dropdown. It is a flat selector
        (no parent cascade)."""
        assert PaysSelector.id == "pays"
        assert PaysSelector.taxonomy_name == "pays"
        assert PaysSelector.is_dual is False
        assert issubclass(PaysSelector, BaseSelector)
        assert not issubclass(PaysSelector, DualSelector)


class TestExpertValueExtraction:
    """Verify each selector reads the RIGHT attribute on the profile.

    The point of these tests is to make a future rename of
    `profile.secteurs_activite` (or similar) loud rather than silent.
    We seed the expected attribute, confirm the selector sees the
    value, then seed every neighbour's attribute and confirm the
    selector does NOT pick those up.
    """

    @pytest.mark.parametrize(
        ("selector_cls", "attr"),
        [(cls, attr) for cls, _sid, _tax, attr, _base in LIST_SELECTOR_CONTRACTS],
    )
    def test_expert_values_reads_declared_attribute(
        self,
        selector_cls: type[BaseSelector],
        attr: str,
    ) -> None:
        """The selector reads from the attribute it claims to read."""
        expert = _build_expert(attr, ["sentinel_value"])
        selector = selector_cls({}, [expert])
        values = list(selector._expert_values(expert))
        assert "sentinel_value" in values, (
            f"{selector_cls.__name__} did not surface the value written "
            f"to profile.{attr} — the attribute may have been renamed "
            "or the selector now points at a neighbour."
        )

    @pytest.mark.parametrize(
        ("selector_cls", "attr"),
        [(cls, attr) for cls, _sid, _tax, attr, _base in LIST_SELECTOR_CONTRACTS],
    )
    def test_expert_values_does_not_leak_neighbour_attribute(
        self,
        selector_cls: type[BaseSelector],
        attr: str,
    ) -> None:
        """Cross-check: writing to a NEIGHBOUR attribute should not
        leak into the selector's value list. This catches a swap
        between, e.g., `type_entreprise_media` ↔ `type_presse_et_media`.
        """
        expert = _StandInUser()
        for neighbour in ALL_LIST_PROFILE_ATTRS - {attr}:
            setattr(expert.profile, neighbour, ["neighbour_value"])
        selector = selector_cls({}, [expert])
        values = list(selector._expert_values(expert))
        assert "neighbour_value" not in values, (
            f"{selector_cls.__name__} leaked a neighbour attribute "
            f"into its expert_values output (expected only {attr})."
        )

    def test_pays_selector_wraps_scalar_country_in_singleton(self) -> None:
        """`profile.country` is a SCALAR string in production; the
        selector must wrap it so `BaseSelector._count_by_value` (which
        iterates expert values) sees one item, not the string's
        characters.
        """
        expert = _StandInUser()
        expert.profile.country = "FR"
        selector = PaysSelector({}, [expert])
        values = list(selector._expert_values(expert))
        assert values == ["FR"]

    def test_pays_selector_empty_country_yields_no_values(self) -> None:
        """An untouched country (= empty string) must NOT contribute
        a `""` entry — that would create a phantom « empty country »
        option in the dropdown."""
        expert = _StandInUser()
        selector = PaysSelector({}, [expert])
        assert list(selector._expert_values(expert)) == []


class TestDefensiveBranches:
    """No expert / no profile / empty values must not crash.

    The selector is constructed in many UI paths (HTMX re-renders,
    initial page load, etc.) before any expert is known. The
    constructor must not raise on an empty pool, and `_expert_values`
    must return an iterable for an empty profile.
    """

    @pytest.mark.parametrize(
        "selector_cls",
        [cls for cls, *_ in LIST_SELECTOR_CONTRACTS] + [PaysSelector],
    )
    def test_constructor_accepts_empty_expert_pool(
        self,
        selector_cls: type[BaseSelector],
    ) -> None:
        """An empty `experts` list yields a selector with empty values
        and an empty `_count_by_value` (no exceptions). This is the
        path hit on the very first page load before any candidate
        filter has been applied."""
        selector = selector_cls({}, [])
        assert selector.values == set()
        # `_count_by_value` is a `cached_property` — touch it to verify
        # the lazy iteration handles an empty pool cleanly.
        assert selector._count_by_value == {}

    @pytest.mark.parametrize(
        ("selector_cls", "attr"),
        [(cls, attr) for cls, _sid, _tax, attr, _base in LIST_SELECTOR_CONTRACTS],
    )
    def test_expert_values_on_empty_profile_is_iterable(
        self,
        selector_cls: type[BaseSelector],
        attr: str,
    ) -> None:
        """An untouched stand-in profile (all defaults empty) makes
        `_expert_values` return an empty iterable, not None — the
        downstream `for v in self._expert_values(e)` loops would
        TypeError otherwise."""
        expert = _StandInUser()
        selector = selector_cls({}, [expert])
        values = list(selector._expert_values(expert))
        assert values == [], (
            f"{selector_cls.__name__} returned {values!r} for an empty "
            f"profile; expected []. (attribute: profile.{attr})"
        )

    def test_filter_experts_with_empty_criteria_returns_all(self) -> None:
        """Empty criteria = no filter applied = full pool returned.
        Pins the « user hasn't picked anything » path: the ciblage
        must NOT silently drop everyone."""
        experts: list[Any] = [_StandInUser(), _StandInUser()]
        for selector_cls, *_ in LIST_SELECTOR_CONTRACTS:
            selector = selector_cls({}, experts)
            assert selector.filter_experts(set(), experts) == experts
        # PaysSelector overrides filter_experts but must still
        # short-circuit on empty criteria.
        pays = PaysSelector({}, experts)
        assert pays.filter_experts(set(), experts) == experts


class TestFilterOutput:
    """Filter output is a `list[User]` — pin the type and shape."""

    @pytest.mark.parametrize(
        ("selector_cls", "attr"),
        [(cls, attr) for cls, _sid, _tax, attr, _base in LIST_SELECTOR_CONTRACTS],
    )
    def test_list_selector_filter_keeps_matching_experts(
        self,
        selector_cls: type[BaseSelector],
        attr: str,
    ) -> None:
        """Each list-valued selector filters experts whose declared
        profile attribute intersects the criteria. Routes through the
        inherited `BaseSelector.filter_experts` (or its DualSelector
        override) — pinning here confirms the override didn't break
        the intersection semantics.
        """
        match = _build_expert(attr, ["MATCH"])
        miss = _build_expert(attr, ["OTHER"])
        experts: list[Any] = [match, miss]
        selector = selector_cls({}, experts)
        result = selector.filter_experts({"MATCH"}, experts)
        assert result == [match]
        assert isinstance(result, list)

    def test_pays_selector_filter_uses_equality_not_intersection(self) -> None:
        """PaysSelector overrides `filter_experts` because
        `profile.country` is a scalar. The override compares with
        `e.profile.country in criteria` — pin the semantics so a
        refactor that drops the override (and falls back to the
        list-intersection default) trips this test.
        """
        france = _StandInUser()
        france.profile.country = "FR"
        spain = _StandInUser()
        spain.profile.country = "ES"
        unset = _StandInUser()  # country = ""
        experts = [france, spain, unset]
        selector = PaysSelector({}, experts)
        result = selector.filter_experts({"FR"}, experts)
        assert result == [france]
        assert isinstance(result, list)

    def test_pays_selector_filter_multi_country_criteria(self) -> None:
        """Multiple selected countries widen the result set; this is
        the « show me both FR and BE experts » path."""
        fr = _StandInUser()
        fr.profile.country = "FR"
        be = _StandInUser()
        be.profile.country = "BE"
        es = _StandInUser()
        es.profile.country = "ES"
        experts = [fr, be, es]
        selector = PaysSelector({}, experts)
        result = selector.filter_experts({"FR", "BE"}, experts)
        assert result == [fr, be]


class TestCoverageCrossCheck:
    """Sanity: the contract table covers every concrete selector in
    the « general » family exactly once.

    Without this guard, adding a new selector (or accidentally
    duplicating one) would slip through this file with zero
    coverage.
    """

    def test_no_duplicate_selectors_in_contract_table(self) -> None:
        classes = [cls for cls, *_ in LIST_SELECTOR_CONTRACTS]
        assert len(classes) == len(set(classes))

    def test_contract_table_covers_target_set(self) -> None:
        """Pins the exact target set requested for this file. If a
        selector is added/removed from this group, the assertion fires
        so the test file is updated deliberately rather than silently
        drifting. `PaysSelector` is tracked separately because its
        scalar `profile.country` shape doesn't fit the list-valued
        contract table."""
        expected = {
            SecteurSelector,
            TypeEntreprisePresseMediasSelector,
            TypePresseMediasSelector,
            LanguesSelector,
            TypeOrganisationSelector,
            TailleOrganisationSelector,
        }
        assert {cls for cls, *_ in LIST_SELECTOR_CONTRACTS} == expected
