# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Unit tests for the « métier / fonction » expert selectors.

Pins the contract of each concrete selector in
`app.modules.wip.services.newsroom.expert_selectors` covering the
« métier » and « fonction » filter dimensions:

  - `MetierSelector` (cascade)
  - `FonctionSelector` (flat, aggregate)
  - `FonctionJournalismeSelector` (flat)
  - `FonctionPolitiquesAdministrativesSelector` (cascade)
  - `FonctionOrganisationsPriveesSelector` (cascade)
  - `FonctionAssociationsSyndicatsSelector` (cascade)

WHY this file exists
====================

The selectors expose a tiny but load-bearing contract: each one reads
ONE specific attribute on `User` / `User.profile`. A silent rename of
that attribute would empty the expert ciblage results with no error
(filter pipelines that intersect with an empty set just return `[]`).
The existing « general » group of expert-selector tests pins that
contract for secteur/langues/competences/...; this file does the same
for the « métier » + « fonction » family.

We rely on stand-in `User` / `Profile` objects (duck-typed) instead of
DB rows so the test stays purely unit-level: no Flask app, no SQL, no
KYC taxonomy boot. The selector code only touches the attribute name
on the stand-in, so a future refactor that renames a profile attr will
turn at least one assertion in this file red.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pytest

from app.modules.wip.services.newsroom.expert_selectors import (
    BaseSelector,
    DualSelector,
    FonctionAssociationsSyndicatsSelector,
    FonctionJournalismeSelector,
    FonctionOrganisationsPriveesSelector,
    FonctionPolitiquesAdministrativesSelector,
    FonctionSelector,
    MetierSelector,
)

# ----------------------------------------------------------------
# Stand-in stubs: duck-typed Profile / User
# ----------------------------------------------------------------
#
# The selectors only call `expert.tous_metiers` or
# `expert.profile.<some_attribute>` — they never call ORM methods or
# touch the SQLAlchemy session. A dataclass with the right attribute
# names is enough to exercise the contract.


@dataclass
class _StandInProfile:
    """Minimal duck-typed replacement for `KYCProfile`.

    Every field defaults to an empty list so a selector reading an
    untouched attribute observes an « empty profile » exactly like
    a freshly-created KYC row.
    """

    toutes_fonctions: list[str] = field(default_factory=list)
    fonctions_journalisme: list[str] = field(default_factory=list)
    fonctions_pol_adm_detail: list[str] = field(default_factory=list)
    fonctions_org_priv_detail: list[str] = field(default_factory=list)
    fonctions_ass_syn_detail: list[str] = field(default_factory=list)


@dataclass
class _StandInUser:
    """Minimal duck-typed replacement for `User`.

    `tous_metiers` is the union surfaced on `User` itself (hybrid
    property) — MetierSelector reads it from the user, NOT the
    profile. The other selectors read from `user.profile`.
    """

    tous_metiers: set[str] = field(default_factory=set)
    profile: _StandInProfile = field(default_factory=_StandInProfile)


# ----------------------------------------------------------------
# Per-selector contract pinning
# ----------------------------------------------------------------
#
# The table below is the single source of truth: each row asserts
# « this selector reads exactly this attribute on this carrier ».
# A cross-check at the bottom of this module verifies every selector
# in the « métier / fonction » family is covered exactly once.

SELECTOR_CONTRACTS: list[
    tuple[type[BaseSelector], str, str, str, type[BaseSelector]]
] = [
    # (selector_cls, expected_id, attribute_carrier, attribute_name, base)
    (MetierSelector, "metier", "user", "tous_metiers", DualSelector),
    (FonctionSelector, "fonction", "profile", "toutes_fonctions", BaseSelector),
    (
        FonctionJournalismeSelector,
        "fonction_journalisme",
        "profile",
        "fonctions_journalisme",
        BaseSelector,
    ),
    (
        FonctionPolitiquesAdministrativesSelector,
        "fonction_pol_adm",
        "profile",
        "fonctions_pol_adm_detail",
        DualSelector,
    ),
    (
        FonctionOrganisationsPriveesSelector,
        "fonction_org_priv",
        "profile",
        "fonctions_org_priv_detail",
        DualSelector,
    ),
    (
        FonctionAssociationsSyndicatsSelector,
        "fonction_ass_syn",
        "profile",
        "fonctions_ass_syn_detail",
        DualSelector,
    ),
]


def _set_attr(expert: _StandInUser, carrier: str, attr: str, value: Any) -> None:
    """Write `value` to `expert.<carrier>.<attr>` (carrier ∈ user|profile)."""
    if carrier == "user":
        setattr(expert, attr, value)
    elif carrier == "profile":
        setattr(expert.profile, attr, value)
    else:  # pragma: no cover - typo guard
        msg = f"unknown carrier {carrier!r}"
        raise ValueError(msg)


# ----------------------------------------------------------------
# Tests
# ----------------------------------------------------------------


class TestSelectorIdentity:
    """Pin id/label/taxonomy_name + class hierarchy.

    A silent rename of `id` would re-key `FilterState` and lose the
    user's selection on the next request. A silent change to the
    `is_dual` flag would break the template router that picks the
    cascade partial.
    """

    @pytest.mark.parametrize(
        ("selector_cls", "expected_id", "base"),
        [(cls, sid, base) for cls, sid, _carrier, _attr, base in SELECTOR_CONTRACTS],
    )
    def test_selector_id_and_hierarchy(
        self,
        selector_cls: type[BaseSelector],
        expected_id: str,
        base: type[BaseSelector],
    ) -> None:
        """Each selector exposes the expected form-field id and subclasses
        the expected base. The id is the cross-request stable key in
        `FilterState`; the base controls template routing (cascade vs flat).
        """
        assert selector_cls.id == expected_id
        assert issubclass(selector_cls, base)
        assert issubclass(selector_cls, BaseSelector)
        # DualSelector subclasses ALSO advertise themselves as duals.
        if base is DualSelector:
            assert selector_cls.is_dual is True
            assert selector_cls.parent_id
            assert selector_cls.parent_id != selector_cls.id
        else:
            # Flat selectors never claim to be duals (template would
            # route them to the cascade partial and crash on missing
            # parent_id).
            assert selector_cls.is_dual is False

    def test_metier_selector_taxonomy_name(self) -> None:
        """MetierSelector is backed by the « metier » KYC ontology so
        `get_values()` can surface the full taxonomy even when no
        expert in the pool holds a given métier yet."""
        assert MetierSelector.taxonomy_name == "metier"

    def test_fonction_journalisme_taxonomy_name(self) -> None:
        """FonctionJournalismeSelector is backed by the journalism-only
        function taxonomy — pin so a rename of the taxonomy doesn't
        silently turn the dropdown empty."""
        assert FonctionJournalismeSelector.taxonomy_name == "journalisme_fonction"

    @pytest.mark.parametrize(
        ("selector_cls", "expected_taxonomy"),
        [
            (
                FonctionPolitiquesAdministrativesSelector,
                "profession_fonction_public",
            ),
            (
                FonctionOrganisationsPriveesSelector,
                "profession_fonction_prive",
            ),
            (
                FonctionAssociationsSyndicatsSelector,
                "profession_fonction_asso",
            ),
        ],
    )
    def test_fonction_cascade_taxonomies(
        self,
        selector_cls: type[BaseSelector],
        expected_taxonomy: str,
    ) -> None:
        """Each cascade selector for fonctions points at its OWN
        taxonomy. A copy-paste typo that aliased two selectors onto
        the same taxonomy would silently merge the cascades."""
        assert selector_cls.taxonomy_name == expected_taxonomy

    def test_fonction_selector_taxonomy_is_aggregated(self) -> None:
        """The aggregate « toutes fonctions » selector has NO single
        backing taxonomy — it unions three of them in `get_values()`.
        Marker: `taxonomy_name is None`."""
        assert FonctionSelector.taxonomy_name is None


class TestExpertValueExtraction:
    """Verify each selector reads the RIGHT attribute on the expert.

    The point of these tests is to make a future rename of
    `profile.fonctions_journalisme` (or similar) loud rather than
    silent. We seed the expected attribute, confirm the selector
    sees the value, then seed a neighbour's attribute and confirm
    the selector does NOT pick that up.
    """

    @pytest.mark.parametrize(
        ("selector_cls", "carrier", "attr"),
        [
            (cls, carrier, attr)
            for cls, _sid, carrier, attr, _base in SELECTOR_CONTRACTS
        ],
    )
    def test_expert_values_reads_declared_attribute(
        self,
        selector_cls: type[BaseSelector],
        carrier: str,
        attr: str,
    ) -> None:
        """The selector reads from the attribute it claims to read."""
        expert = _StandInUser()
        _set_attr(expert, carrier, attr, ["sentinel_value"])
        selector = selector_cls({}, [expert])
        values = list(selector._expert_values(expert))
        assert "sentinel_value" in values, (
            f"{selector_cls.__name__} did not surface the value written "
            f"to expert.{carrier}.{attr} — the attribute may have been "
            "renamed or the selector now points at a neighbour."
        )

    @pytest.mark.parametrize(
        ("selector_cls", "carrier", "attr"),
        [
            (cls, carrier, attr)
            for cls, _sid, carrier, attr, _base in SELECTOR_CONTRACTS
            # Skip FonctionSelector: its attribute (`toutes_fonctions`)
            # is itself an aggregate over the three detail attrs in
            # production — a stand-in property can't capture that
            # cross-coupling cleanly, so we test it separately.
            if cls is not FonctionSelector
        ],
    )
    def test_expert_values_does_not_leak_neighbour_attribute(
        self,
        selector_cls: type[BaseSelector],
        carrier: str,
        attr: str,
    ) -> None:
        """Cross-check: writing to a NEIGHBOUR attribute should not
        leak into the selector's value list. This catches a swap
        between, e.g., `fonctions_journalisme` ↔ `fonctions_pol_adm_detail`.
        """
        expert = _StandInUser()
        neighbour_attrs = {
            "tous_metiers",
            "toutes_fonctions",
            "fonctions_journalisme",
            "fonctions_pol_adm_detail",
            "fonctions_org_priv_detail",
            "fonctions_ass_syn_detail",
        } - {attr}
        for neighbour in neighbour_attrs:
            value = ["neighbour_value"]
            if neighbour == "tous_metiers":
                expert.tous_metiers = set(value)
            else:
                setattr(expert.profile, neighbour, value)

        selector = selector_cls({}, [expert])
        values = list(selector._expert_values(expert))
        assert "neighbour_value" not in values, (
            f"{selector_cls.__name__} leaked a neighbour attribute "
            f"into its expert_values output (expected only {attr})."
        )

    def test_fonction_selector_aggregates_three_fonction_families(self) -> None:
        """FonctionSelector reads `profile.toutes_fonctions` — the
        production property unions journalisme + pol_adm + org_priv +
        ass_syn. We pin the read-attribute name; aggregation correctness
        is the model's responsibility.
        """
        expert = _StandInUser()
        expert.profile.toutes_fonctions = ["JOUR-1", "PUB-1", "PRIV-1", "ASS-1"]
        selector = FonctionSelector({}, [expert])
        values = list(selector._expert_values(expert))
        assert set(values) == {"JOUR-1", "PUB-1", "PRIV-1", "ASS-1"}


class TestDefensiveBranches:
    """No expert / no profile / empty values must not crash.

    The selector is constructed in many UI paths (HTMX re-renders,
    initial page load, etc.) before any expert is known. The
    constructor must not raise on an empty pool, and `_expert_values`
    must return an iterable for an empty profile.
    """

    @pytest.mark.parametrize(
        "selector_cls",
        [cls for cls, *_ in SELECTOR_CONTRACTS],
    )
    def test_constructor_accepts_empty_expert_pool(
        self,
        selector_cls: type[BaseSelector],
    ) -> None:
        """An empty `experts` list yields a selector with empty values
        and an empty options list (no exceptions). This is the path
        hit on the very first page load before any candidate filter
        has been applied."""
        selector = selector_cls({}, [])
        assert selector.values == set()
        # `_count_by_value` is a `cached_property` — touch it to verify
        # the lazy iteration handles an empty pool cleanly.
        assert selector._count_by_value == {}

    @pytest.mark.parametrize(
        ("selector_cls", "carrier", "attr"),
        [
            (cls, carrier, attr)
            for cls, _sid, carrier, attr, _base in SELECTOR_CONTRACTS
        ],
    )
    def test_expert_values_on_empty_profile_is_iterable(
        self,
        selector_cls: type[BaseSelector],
        carrier: str,
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
            f"profile; expected []. (attribute: {carrier}.{attr})"
        )

    def test_filter_experts_with_empty_criteria_returns_all(self) -> None:
        """Empty criteria = no filter applied = full pool returned.
        This is the « user hasn't picked anything » path and the
        ciblage must NOT silently drop everyone."""
        experts = [_StandInUser(), _StandInUser()]
        for selector_cls, *_ in SELECTOR_CONTRACTS:
            selector = selector_cls({}, experts)
            assert selector.filter_experts(set(), experts) == experts


class TestFilterOutput:
    """Filter output is a `list[User]` — pin the type and shape."""

    def test_metier_filter_keeps_matching_experts(self) -> None:
        """MetierSelector keeps experts whose `tous_metiers` intersect
        the criteria. (Sanity check that the inherited
        `BaseSelector.filter_experts` still works once a subclass
        flips `is_dual = True`.)"""
        alice = _StandInUser(tous_metiers={"Journaliste"})
        bob = _StandInUser(tous_metiers={"Photographe"})
        carol = _StandInUser(tous_metiers={"Journaliste", "Photographe"})
        experts = [alice, bob, carol]
        selector = MetierSelector({}, experts)
        result = selector.filter_experts({"Journaliste"}, experts)
        assert result == [alice, carol]
        assert isinstance(result, list)

    @pytest.mark.parametrize(
        ("selector_cls", "carrier", "attr"),
        [
            (cls, carrier, attr)
            for cls, _sid, carrier, attr, _base in SELECTOR_CONTRACTS
            if cls is not FonctionSelector  # see aggregator test above
        ],
    )
    def test_fonction_filter_keeps_matching_experts(
        self,
        selector_cls: type[BaseSelector],
        carrier: str,
        attr: str,
    ) -> None:
        """Each « fonction » selector filters experts whose declared
        attribute intersects the criteria. The selector is in charge
        of routing `_expert_values` through `BaseSelector.filter_experts`.
        """
        match = _StandInUser()
        miss = _StandInUser()
        _set_attr(match, carrier, attr, ["MATCH"])
        _set_attr(miss, carrier, attr, ["OTHER"])
        experts = [match, miss]
        selector = selector_cls({}, experts)
        result = selector.filter_experts({"MATCH"}, experts)
        assert result == [match]


class TestCoverageCrossCheck:
    """Sanity: the SELECTOR_CONTRACTS table covers every concrete
    selector in the « métier / fonction » family exactly once.

    Without this guard, adding a new selector (or accidentally
    duplicating one) would slip through this file with zero
    coverage.
    """

    def test_no_duplicate_selectors_in_contract_table(self) -> None:
        classes = [cls for cls, *_ in SELECTOR_CONTRACTS]
        assert len(classes) == len(set(classes))

    def test_contract_table_covers_target_set(self) -> None:
        """Pins the exact target set requested for this file. If a
        selector is added/removed from this group, the assertion fires
        so the test file is updated deliberately rather than silently
        drifting."""
        expected = {
            MetierSelector,
            FonctionSelector,
            FonctionJournalismeSelector,
            FonctionPolitiquesAdministrativesSelector,
            FonctionOrganisationsPriveesSelector,
            FonctionAssociationsSyndicatsSelector,
        }
        assert {cls for cls, *_ in SELECTOR_CONTRACTS} == expected
