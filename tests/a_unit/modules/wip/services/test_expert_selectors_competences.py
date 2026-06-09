# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Unit tests for the « compétences » expert selectors.

Pins the contract of the concrete selectors in
`app.modules.wip.services.newsroom.expert_selectors` that cover the
« compétences » filter dimension (plus the closely-related métier /
fonction selectors that share their stand-in scaffolding):

  - `CompetencesGeneralesSelector` (cascade)
  - `CompetencesJournalismeSelector` (flat)
  - `MetierSelector` (cascade)
  - `FonctionSelector` (flat, aggregate)
  - `FonctionJournalismeSelector` (flat)
  - `FonctionPolitiquesAdministrativesSelector` (cascade)
  - `FonctionOrganisationsPriveesSelector` (cascade)
  - `FonctionAssociationsSyndicatsSelector` (cascade)

WHY this file exists
====================

Each selector reads ONE specific attribute on `User` / `User.profile`.
A silent rename of that attribute would empty the expert ciblage
results with no error (filter pipelines intersecting with an empty
set just return `[]`). This file pins the contract for the
« compétences » family + the métier / fonction selectors that share
the same shape and stand-in scaffolding.

The selectors already accept dependency-injected loaders
(`taxonomy_loader`, `dual_taxonomy_loader`) via keyword-only optional
constructor arguments. That gives us a clean unit boundary with NO
Flask app, NO SQL, NO KYC ontology boot, and NO mock library: tests
pass plain callables and duck-typed stand-in objects.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pytest

from app.modules.wip.services.newsroom.expert_selectors import (
    BaseSelector,
    CompetencesGeneralesSelector,
    CompetencesJournalismeSelector,
    DualSelector,
    FilterOption,
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
# The selectors only access `expert.tous_metiers` or
# `expert.profile.<some_attribute>` — never ORM methods, never the
# SQLAlchemy session. A dataclass with the right attribute names is
# enough to exercise the contract.


@dataclass
class _StandInProfile:
    """Minimal duck-typed replacement for `KYCProfile`.

    Every field defaults to an empty list so a selector reading an
    untouched attribute observes an « empty profile » identical to
    a freshly-created KYC row.
    """

    competences: list[str] = field(default_factory=list)
    competences_journalisme: list[str] = field(default_factory=list)
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
    profile. All other selectors here read from `user.profile`.
    """

    tous_metiers: set[str] = field(default_factory=set)
    profile: _StandInProfile = field(default_factory=_StandInProfile)


# ----------------------------------------------------------------
# Per-selector contract pinning
# ----------------------------------------------------------------
#
# The table below is the single source of truth: each row asserts
# « this selector reads exactly this attribute on this carrier ».
# A cross-check at the bottom of this module verifies the target
# set requested for this file is covered exactly once.

SELECTOR_CONTRACTS: list[
    tuple[type[BaseSelector], str, str, str, type[BaseSelector]]
] = [
    # (selector_cls, expected_id, attribute_carrier, attribute_name, base)
    (
        CompetencesGeneralesSelector,
        "competences",
        "profile",
        "competences",
        DualSelector,
    ),
    (
        CompetencesJournalismeSelector,
        "competences_journalisme",
        "profile",
        "competences_journalisme",
        BaseSelector,
    ),
    (MetierSelector, "metier", "user", "tous_metiers", DualSelector),
    (
        FonctionSelector,
        "fonction",
        "profile",
        "toutes_fonctions",
        BaseSelector,
    ),
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
# Tests focused on « compétences »
# ----------------------------------------------------------------


class TestCompetencesSelectorIdentity:
    """Pin id / label / taxonomy_name / hierarchy for the compétences
    selectors.

    The « compétences » filter dimension is split in two: a general
    cascade backed by the KYC `competence_expert` ontology, and a
    journalism-only flat selector backed by `journalisme_competence`.
    A copy-paste typo that aliased one onto the other would silently
    merge the two dropdowns.
    """

    def test_competences_generales_metadata(self) -> None:
        assert CompetencesGeneralesSelector.id == "competences"
        assert CompetencesGeneralesSelector.parent_id == "competences_parent"
        assert CompetencesGeneralesSelector.taxonomy_name == "competence_expert"
        assert CompetencesGeneralesSelector.is_dual is True
        assert issubclass(CompetencesGeneralesSelector, DualSelector)

    def test_competences_journalisme_metadata(self) -> None:
        assert CompetencesJournalismeSelector.id == "competences_journalisme"
        assert CompetencesJournalismeSelector.taxonomy_name == "journalisme_competence"
        assert CompetencesJournalismeSelector.is_dual is False
        assert issubclass(CompetencesJournalismeSelector, BaseSelector)
        assert not issubclass(CompetencesJournalismeSelector, DualSelector)

    def test_competences_selectors_use_distinct_taxonomies(self) -> None:
        """The two compétences selectors must point at DIFFERENT taxonomies:
        the cascade backs the general « famille / compétence » KYC tree,
        the flat one backs a journalism-only short list. A merge would
        silently produce duplicate options in the dropdown.
        """
        assert (
            CompetencesGeneralesSelector.taxonomy_name
            != CompetencesJournalismeSelector.taxonomy_name
        )


class TestCompetencesExpertValueExtraction:
    """The compétences selectors read EXACTLY their declared profile
    attribute (`profile.competences` vs `profile.competences_journalisme`).
    """

    def test_competences_generales_reads_profile_competences(self) -> None:
        expert = _StandInUser()
        expert.profile.competences = ["Data / Python", "Design / UX"]
        selector = CompetencesGeneralesSelector({}, [expert])
        values = list(selector._expert_values(expert))
        assert values == ["Data / Python", "Design / UX"]

    def test_competences_journalisme_reads_profile_competences_journalisme(
        self,
    ) -> None:
        expert = _StandInUser()
        expert.profile.competences_journalisme = ["Investigation", "Reportage"]
        selector = CompetencesJournalismeSelector({}, [expert])
        values = list(selector._expert_values(expert))
        assert values == ["Investigation", "Reportage"]

    def test_competences_generales_does_not_leak_journalisme(self) -> None:
        """Cross-check: writing to `competences_journalisme` must not
        leak into the general selector. Catches a swap between the
        two profile attributes.
        """
        expert = _StandInUser()
        expert.profile.competences_journalisme = ["Investigation"]
        selector = CompetencesGeneralesSelector({}, [expert])
        assert list(selector._expert_values(expert)) == []

    def test_competences_journalisme_does_not_leak_generales(self) -> None:
        expert = _StandInUser()
        expert.profile.competences = ["Data / Python"]
        selector = CompetencesJournalismeSelector({}, [expert])
        assert list(selector._expert_values(expert)) == []


class TestCompetencesFilterAndOptions:
    """End-to-end shape: the selectors filter experts and render
    `FilterOption` rows with the documented `(N)` count badge.
    """

    def test_competences_generales_filter_keeps_matching_experts(self) -> None:
        alice = _StandInUser()
        bob = _StandInUser()
        alice.profile.competences = ["Data / Python"]
        bob.profile.competences = ["Design / UX"]
        experts = [alice, bob]
        selector = CompetencesGeneralesSelector({}, experts)
        result = selector.filter_experts({"Data / Python"}, experts)
        assert result == [alice]

    def test_competences_journalisme_filter_keeps_matching_experts(self) -> None:
        alice = _StandInUser()
        bob = _StandInUser()
        alice.profile.competences_journalisme = ["Investigation"]
        bob.profile.competences_journalisme = ["Reportage"]
        experts = [alice, bob]
        selector = CompetencesJournalismeSelector({}, experts)
        result = selector.filter_experts({"Investigation"}, experts)
        assert result == [alice]
        assert isinstance(result, list)

    def test_competences_journalisme_options_carry_count_badge(self) -> None:
        """A taxonomy entry held by experts must appear in the options
        with a `(N)` badge. The injected `loader` callable IS the
        unit-test boundary — no Flask, no SQL, no patching.
        """
        loader_calls: list[str] = []

        def fake_loader(name: str) -> list[str]:
            loader_calls.append(name)
            return ["Investigation", "Reportage", "Unused"]

        alice = _StandInUser()
        bob = _StandInUser()
        alice.profile.competences_journalisme = ["Investigation"]
        bob.profile.competences_journalisme = ["Investigation", "Reportage"]
        selector = CompetencesJournalismeSelector(
            {}, [alice, bob], taxonomy_loader=fake_loader
        )
        options = selector.options
        assert loader_calls == ["journalisme_competence"]
        # `Unused` is in the taxonomy but held by no expert -> filtered out.
        labels = {opt.label for opt in options}
        assert labels == {"Investigation (2)", "Reportage (1)"}
        ids = {opt.id for opt in options}
        assert ids == {"Investigation", "Reportage"}
        assert all(isinstance(opt, FilterOption) for opt in options)

    def test_competences_journalisme_preserves_user_selection_at_count_zero(
        self,
    ) -> None:
        """A currently-selected value with zero matching experts must
        STILL appear in the options (with count 0 and `selected=` set)
        so the user's chip survives an HTMX re-render.
        """

        def fake_loader(name: str) -> list[str]:
            return []

        expert = _StandInUser()
        # User picked "Investigation" but no expert holds it (yet).
        selector = CompetencesJournalismeSelector(
            {"competences_journalisme": ["Investigation"]},
            [expert],
            taxonomy_loader=fake_loader,
        )
        opts = selector.options
        assert len(opts) == 1
        assert opts[0].id == "Investigation"
        assert opts[0].label == "Investigation (0)"
        assert opts[0].selected == "selected"


class TestCompetencesGeneralesCascade:
    """The cascade selector renders parent + child rows via
    `get_dual_tom_choices_for_js()`, fed by the injected dual loader.
    No KYC ontology boot, no Flask app.
    """

    def test_get_dual_tom_choices_uses_injected_loader(self) -> None:
        recorded: list[str] = []

        def fake_dual_loader(name: str) -> dict[str, Any]:
            recorded.append(name)
            return {
                "field1": [("Data", "Data"), ("Design", "Design")],
                "field2": {
                    "Data": [
                        ("Data / Python", "Data / Python"),
                        ("Data / SQL", "Data / SQL"),
                    ],
                    "Design": [("Design / UX", "Design / UX")],
                },
            }

        alice = _StandInUser()
        bob = _StandInUser()
        alice.profile.competences = ["Data / Python"]
        bob.profile.competences = ["Data / Python", "Design / UX"]
        selector = CompetencesGeneralesSelector(
            {}, [alice, bob], dual_taxonomy_loader=fake_dual_loader
        )
        result = selector.get_dual_tom_choices_for_js()

        assert recorded == ["competence_expert"]
        # `Data / SQL` is in the taxonomy but held by no expert -> dropped.
        child_values = {c["value"] for c in result["field2"]}
        assert child_values == {"Data / Python", "Design / UX"}
        # Parent counts are SUMS of surviving children.
        parents = {p["value"]: p["label"] for p in result["field1"]}
        assert parents == {"Data": "Data (2)", "Design": "Design (1)"}


# ----------------------------------------------------------------
# Broad coverage: the requested family of selectors
# ----------------------------------------------------------------


class TestSelectorIdentity:
    """Pin id / hierarchy / is_dual flag for the requested selector
    family. A silent rename of `id` would re-key `FilterState` and
    lose the user's selection on the next request.
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
        assert selector_cls.id == expected_id
        assert issubclass(selector_cls, base)
        assert issubclass(selector_cls, BaseSelector)
        if base is DualSelector:
            assert selector_cls.is_dual is True
            assert selector_cls.parent_id
            assert selector_cls.parent_id != selector_cls.id
        else:
            assert selector_cls.is_dual is False


class TestExpertValueExtraction:
    """Verify each selector reads the RIGHT attribute on the expert."""

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
        expert = _StandInUser()
        _set_attr(expert, carrier, attr, ["sentinel_value"])
        selector = selector_cls({}, [expert])
        values = list(selector._expert_values(expert))
        assert "sentinel_value" in values, (
            f"{selector_cls.__name__} did not surface the value written "
            f"to expert.{carrier}.{attr} — the attribute may have been "
            "renamed or the selector now points at a neighbour."
        )


class TestDefensiveBranches:
    """No expert / no profile / empty values must not crash."""

    @pytest.mark.parametrize(
        "selector_cls",
        [cls for cls, *_ in SELECTOR_CONTRACTS],
    )
    def test_constructor_accepts_empty_expert_pool(
        self,
        selector_cls: type[BaseSelector],
    ) -> None:
        selector = selector_cls({}, [])
        assert selector.values == set()
        # `_count_by_value` is a `cached_property` — touch it to verify
        # lazy iteration handles an empty pool cleanly.
        assert selector._count_by_value == {}

    @pytest.mark.parametrize(
        "selector_cls",
        [cls for cls, *_ in SELECTOR_CONTRACTS],
    )
    def test_filter_experts_with_empty_criteria_returns_all(
        self,
        selector_cls: type[BaseSelector],
    ) -> None:
        experts = [_StandInUser(), _StandInUser()]
        selector = selector_cls({}, experts)
        assert selector.filter_experts(set(), experts) == experts


class TestCoverageCrossCheck:
    """Sanity: the SELECTOR_CONTRACTS table covers the requested target
    set exactly once. Without this guard, adding a new selector (or
    accidentally duplicating one) would slip through this file with
    zero coverage.
    """

    def test_no_duplicate_selectors_in_contract_table(self) -> None:
        classes = [cls for cls, *_ in SELECTOR_CONTRACTS]
        assert len(classes) == len(set(classes))

    def test_contract_table_covers_target_set(self) -> None:
        expected = {
            CompetencesGeneralesSelector,
            CompetencesJournalismeSelector,
            MetierSelector,
            FonctionSelector,
            FonctionJournalismeSelector,
            FonctionPolitiquesAdministrativesSelector,
            FonctionOrganisationsPriveesSelector,
            FonctionAssociationsSyndicatsSelector,
        }
        assert {cls for cls, *_ in SELECTOR_CONTRACTS} == expected
