# Copyright (c) 2021-2026, Abilian SAS & TCA
# SPDX-License-Identifier: AGPL-3.0-only

"""Unit tests for the pure rules in `wip/services/newsroom/expert_filter`.

`ExpertFilterService` is a stateful Flask-coupled orchestrator
(session, repository, HTMX request). The pure pieces — pipeline
composition, form-state merge, selection dedup, form parsing,
section grouping — are extracted at module level so the rules
can be unit-tested without a Flask context, a DB session, or an
HTMX-shaped request.

End-to-end coverage of the orchestrator lives at b_integration
(`test_expert_filter.py`, `test_expert_filter_service.py`). This
file complements them by pinning the individual rules.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.modules.wip.services.newsroom.expert_filter import (
    MAX_SELECTABLE_EXPERTS,
    SelectorSection,
    apply_filter_pipeline,
    build_sections_from_selectors,
    compute_tracked_form_keys,
    merge_expert_selection,
    merge_form_state_into_filter,
    parse_action_from_form,
    parse_expert_ids_from_form,
)

# ---------------------------------------------------------------------------
# Stubs : the helpers operate against duck-typed shapes — we don't
# need a real SQLAlchemy User or BaseSelector subclass.
# ---------------------------------------------------------------------------


def _expert(
    *, id: int, last_name: str = "Dupont", first_name: str = "Marie"
) -> SimpleNamespace:
    return SimpleNamespace(id=id, last_name=last_name, first_name=first_name)


class _StubSelector:
    """Mimic the BaseSelector contract `apply_filter_pipeline` needs.

    Holds a per-expert tag table : an expert matches the filter when
    its id is in the `_tags[criterion]` set for any selected criterion.
    """

    def __init__(
        self,
        id: str,
        *,
        tags: dict[str, set[int]] | None = None,
        is_dual: bool = False,
        parent_id: str = "",
    ) -> None:
        self.id = id
        self._tags = tags or {}
        self.is_dual = is_dual
        self.parent_id = parent_id

    def filter_experts(
        self, criteria: set[str], experts: list[SimpleNamespace]
    ) -> list[SimpleNamespace]:
        allowed: set[int] = set()
        for c in criteria:
            allowed |= self._tags.get(c, set())
        return [e for e in experts if e.id in allowed]


# ---------------------------------------------------------------------------
# apply_filter_pipeline
# ---------------------------------------------------------------------------


class TestApplyFilterPipeline:
    def test_no_active_criteria_returns_capped_list(self) -> None:
        """When every selector has empty state, the journalist sees
        the « no filters » view — return the first `max_count` experts
        unfiltered, no sort, no exclusion. Pin so a refactor that
        unconditionally runs the filter loop doesn't silently change
        the empty-state shape."""
        experts = [_expert(id=i) for i in range(70)]
        result = apply_filter_pipeline(
            experts, state={}, selectors=[_StubSelector("secteur")], max_count=50
        )
        assert len(result) == 50
        # No sort applied — input order preserved.
        assert [e.id for e in result] == list(range(50))

    def test_single_selector_filter_applied(self) -> None:
        experts = [_expert(id=1), _expert(id=2), _expert(id=3)]
        selector = _StubSelector("secteur", tags={"presse": {1, 3}, "media": {2}})
        result = apply_filter_pipeline(
            experts, state={"secteur": ["presse"]}, selectors=[selector]
        )
        # Sorted alphabetically (last_name asc, first_name asc) — all
        # stubs share Dupont/Marie so input order survives.
        assert {e.id for e in result} == {1, 3}

    def test_multiple_selectors_and_intersection(self) -> None:
        experts = [_expert(id=1), _expert(id=2), _expert(id=3)]
        secteur = _StubSelector("secteur", tags={"presse": {1, 2, 3}})
        ville = _StubSelector("ville", tags={"paris": {1, 2}, "lyon": {3}})
        result = apply_filter_pipeline(
            experts,
            state={"secteur": ["presse"], "ville": ["paris"]},
            selectors=[secteur, ville],
        )
        assert {e.id for e in result} == {1, 2}

    def test_string_criterion_is_wrapped_in_set(self) -> None:
        """The form may pass a single string (when only one option is
        picked) instead of a list. The helper must accept both shapes."""
        experts = [_expert(id=1), _expert(id=2)]
        selector = _StubSelector("secteur", tags={"presse": {1}})
        result = apply_filter_pipeline(
            experts,
            state={"secteur": "presse"},  # type: ignore[dict-item]
            selectors=[selector],
        )
        assert {e.id for e in result} == {1}

    def test_excludes_already_selected_experts(self) -> None:
        """The « already selected » experts show up in a separate
        section ; the pipeline drops them so they don't appear in
        both panels (which would let the journalist double-tick them)."""
        experts = [_expert(id=1), _expert(id=2), _expert(id=3)]
        selector = _StubSelector("secteur", tags={"presse": {1, 2, 3}})
        result = apply_filter_pipeline(
            experts,
            state={"secteur": ["presse"], "selected_experts": [2]},
            selectors=[selector],
        )
        assert {e.id for e in result} == {1, 3}

    def test_sorts_by_last_then_first_name(self) -> None:
        experts = [
            _expert(id=1, last_name="Zola", first_name="Émile"),
            _expert(id=2, last_name="Aron", first_name="Raymond"),
            _expert(id=3, last_name="Aron", first_name="Jean"),
        ]
        selector = _StubSelector("secteur", tags={"presse": {1, 2, 3}})
        result = apply_filter_pipeline(
            experts, state={"secteur": ["presse"]}, selectors=[selector]
        )
        assert [e.id for e in result] == [3, 2, 1]

    def test_caps_at_max_count(self) -> None:
        experts = [_expert(id=i, last_name=f"E{i:03}") for i in range(200)]
        selector = _StubSelector("secteur", tags={"presse": set(range(200))})
        result = apply_filter_pipeline(
            experts,
            state={"secteur": ["presse"]},
            selectors=[selector],
            max_count=3,
        )
        assert len(result) == 3

    def test_default_max_is_constant(self) -> None:
        """Pin the documented cap so a refactor that swaps the default
        (« let's render 100 ») doesn't quietly change UI behaviour."""
        assert MAX_SELECTABLE_EXPERTS == 50

    def test_selector_with_empty_criterion_is_skipped(self) -> None:
        """A state entry like `{"secteur": []}` is « user cleared
        the dropdown » — skip rather than apply an empty intersection
        (which would yield no experts)."""
        experts = [_expert(id=1), _expert(id=2)]
        selector = _StubSelector("secteur", tags={"presse": {1}})
        result = apply_filter_pipeline(
            experts, state={"secteur": []}, selectors=[selector]
        )
        # No active filter → returns capped list (un-filtered).
        assert {e.id for e in result} == {1, 2}


# ---------------------------------------------------------------------------
# merge_form_state_into_filter
# ---------------------------------------------------------------------------


class TestMergeFormStateIntoFilter:
    def test_does_not_mutate_input_state(self) -> None:
        original = {"secteur": ["presse"]}
        result = merge_form_state_into_filter(original, {}, tracked_keys={"secteur"})
        # Input untouched ; result is a new dict.
        assert original == {"secteur": ["presse"]}
        assert result is not original

    def test_form_values_overwrite_tracked_keys(self) -> None:
        state = {"secteur": ["presse"]}
        result = merge_form_state_into_filter(
            state, {"secteur": ["media"]}, tracked_keys={"secteur"}
        )
        assert result["secteur"] == ["media"]

    def test_unmentioned_tracked_keys_are_dropped(self) -> None:
        """The drop-on-absence rule is the whole reason this helper
        exists : without it, unchecking a dropdown would leave stale
        state across HTMX re-renders, and the user couldn't escape
        the criterion without clearing the session."""
        state = {"secteur": ["presse"], "metier": ["analyste"]}
        result = merge_form_state_into_filter(
            state,
            {"secteur": ["media"]},  # metier not mentioned
            tracked_keys={"secteur", "metier"},
        )
        assert result == {"secteur": ["media"]}

    def test_empty_form_values_treated_as_drop(self) -> None:
        """Empty-string entries (`[""]`) are the form's way of saying
        « no selection » ; they get filtered out, leaving the key
        unmentioned, which then drops it."""
        state = {"secteur": ["presse"]}
        result = merge_form_state_into_filter(
            state,
            {"secteur": [""]},
            tracked_keys={"secteur"},
        )
        assert "secteur" not in result

    def test_non_tracked_keys_in_payload_ignored(self) -> None:
        """`selector_change`, CSRF tokens, and other non-selector form
        fields must not leak into the filter state."""
        state = {}
        result = merge_form_state_into_filter(
            state,
            {"selector_change": ["1"], "csrf_token": ["abc"]},
            tracked_keys={"secteur"},
        )
        assert result == {}

    def test_preserves_state_keys_outside_tracked(self) -> None:
        """`selected_experts` is part of state but isn't a selector ;
        it must survive a form-merge round-trip."""
        state = {"selected_experts": [1, 2], "secteur": ["presse"]}
        result = merge_form_state_into_filter(
            state,
            {},  # nothing in form
            tracked_keys={"secteur"},  # selected_experts NOT tracked
        )
        # secteur dropped (tracked, unmentioned) ; selected_experts kept.
        assert result == {"selected_experts": [1, 2]}


# ---------------------------------------------------------------------------
# merge_expert_selection
# ---------------------------------------------------------------------------


class TestMergeExpertSelection:
    def test_combines_new_and_existing(self) -> None:
        result = merge_expert_selection([1, 2, 3], [4, 5])
        assert sorted(result) == [1, 2, 3, 4, 5]

    def test_deduplicates(self) -> None:
        result = merge_expert_selection([1, 2], [2, 3])
        assert sorted(result) == [1, 2, 3]

    def test_drops_non_int_legacy_items(self) -> None:
        """`selected_experts` should always be int ids — a legacy
        state where it was overwritten with strings or dicts gets
        cleaned silently."""
        result = merge_expert_selection(["not-an-int", {"oops": True}, 42], [7])
        assert sorted(result) == [7, 42]

    def test_existing_not_a_list_is_ignored(self) -> None:
        """A torn state where selected_experts was overwritten by
        something non-list (None, a dict) must not crash — fall
        back to just the new ids."""
        assert merge_expert_selection(None, [1, 2]) == sorted([1, 2])
        assert merge_expert_selection({"a": 1}, [1, 2]) == sorted([1, 2])

    def test_empty_new_keeps_existing(self) -> None:
        result = merge_expert_selection([1, 2, 3], [])
        assert sorted(result) == [1, 2, 3]


# ---------------------------------------------------------------------------
# parse_action_from_form
# ---------------------------------------------------------------------------


class TestParseActionFromForm:
    def test_finds_action_key(self) -> None:
        assert parse_action_from_form(["action:confirm", "secteur"]) == "confirm"

    def test_returns_empty_string_when_no_action(self) -> None:
        assert parse_action_from_form(["secteur", "metier"]) == ""

    def test_returns_first_action_when_multiple(self) -> None:
        """A submit button click only sends ONE action key, but be
        deterministic if two ever land in the same payload."""
        result = parse_action_from_form(["action:add", "action:confirm"])
        assert result in {"add", "confirm"}  # whichever iteration order picks

    def test_accepts_dict_with_string_keys(self) -> None:
        assert parse_action_from_form({"action:update": "1"}) == "update"

    def test_action_suffix_with_colon_is_preserved_only_to_first(self) -> None:
        """The format is `action:<name>` ; a `<name>` containing
        further colons (unlikely but) keeps everything after the
        first colon."""
        assert parse_action_from_form(["action:bulk:confirm"]) == "bulk:confirm"


# ---------------------------------------------------------------------------
# parse_expert_ids_from_form
# ---------------------------------------------------------------------------


class TestParseExpertIdsFromForm:
    def test_extracts_int_ids(self) -> None:
        result = parse_expert_ids_from_form(["expert:1", "expert:42", "secteur"])
        assert sorted(result) == [1, 42]

    def test_empty_form_yields_empty_list(self) -> None:
        assert parse_expert_ids_from_form([]) == []

    def test_no_expert_keys_yields_empty_list(self) -> None:
        assert parse_expert_ids_from_form(["secteur", "metier"]) == []

    def test_non_numeric_suffix_raises(self) -> None:
        """A form key shaped `expert:abc` is a programmer-error
        signal (bad template / tampered form) ; surface it rather
        than silently dropping."""
        with pytest.raises(ValueError):
            parse_expert_ids_from_form(["expert:not-a-number"])


# ---------------------------------------------------------------------------
# build_sections_from_selectors
# ---------------------------------------------------------------------------


_SECTION_IDS = {
    "Secteurs d'activité et types d'organisation": {
        "secteur",
        "type_organisation",
        "type_entreprise_presse_medias",
        "type_presse_et_media",
        "taille_organisation",
    },
    "Géolocalisation": {"pays", "departement", "ville"},
    "Fonctions": {
        "fonction_pol_adm",
        "fonction_org_priv",
        "fonction_ass_syn",
        "fonction",
        "fonction_journalisme",
    },
    "Métiers, compétences & langues": {
        "metier",
        "competences",
        "competences_journalisme",
        "langues",
    },
}


def _all_selector_stubs() -> list[_StubSelector]:
    """One stub per known selector id — enough to make every section
    populate fully."""
    every_id: list[str] = []
    for ids in _SECTION_IDS.values():
        every_id.extend(ids)
    return [_StubSelector(i) for i in every_id]


class TestBuildSectionsFromSelectors:
    def test_returns_exactly_four_sections(self) -> None:
        """Annie's spec is a 4-thematic layout. Pin so a refactor
        that adds a fifth section is conscious."""
        sections = build_sections_from_selectors(_all_selector_stubs())
        assert len(sections) == 4

    def test_section_titles_match_spec(self) -> None:
        sections = build_sections_from_selectors(_all_selector_stubs())
        titles = [s.title for s in sections]
        assert titles == [
            "Secteurs d'activité et types d'organisation",
            "Géolocalisation",
            "Fonctions",
            "Métiers, compétences & langues",
        ]

    def test_each_section_groups_correct_selector_ids(self) -> None:
        sections = build_sections_from_selectors(_all_selector_stubs())
        for section in sections:
            assert {s.id for s in section.selectors} == _SECTION_IDS[section.title]

    def test_missing_selector_id_is_silently_skipped(self) -> None:
        """The spec calls out 17 selectors but `pick` is tolerant —
        if a future refactor drops one (or renames), the section
        renders with what's available rather than crashing.
        Defensive : the UI must keep working through partial
        refactors."""
        # Only secteur + pays + fonction + metier — one per section.
        selectors = [
            _StubSelector(i) for i in ("secteur", "pays", "fonction", "metier")
        ]
        sections = build_sections_from_selectors(selectors)
        assert [len(s.selectors) for s in sections] == [1, 1, 1, 1]

    def test_returns_selectorsection_dataclasses(self) -> None:
        sections = build_sections_from_selectors(_all_selector_stubs())
        for section in sections:
            assert isinstance(section, SelectorSection)


# ---------------------------------------------------------------------------
# compute_tracked_form_keys
# ---------------------------------------------------------------------------


class TestComputeTrackedFormKeys:
    def test_returns_only_selector_ids_for_non_dual(self) -> None:
        selectors = [_StubSelector("secteur"), _StubSelector("metier")]
        assert compute_tracked_form_keys(selectors) == {"secteur", "metier"}

    def test_includes_parent_id_for_dual_selectors(self) -> None:
        """Dual cascade selectors (parent dropdown narrows the child)
        expose two form fields ; both must round-trip through state
        for the cascade UI to keep its selection across HTMX
        re-renders."""
        selectors = [
            _StubSelector("ville", is_dual=True, parent_id="departement"),
            _StubSelector("secteur"),
        ]
        assert compute_tracked_form_keys(selectors) == {
            "ville",
            "departement",
            "secteur",
        }

    def test_dual_with_blank_parent_id_does_not_add_blank_key(self) -> None:
        """A dual selector that forgot to set `parent_id` should not
        cause an empty-string key in the tracked set — that would
        match every empty form key and bork the merge."""
        selectors = [_StubSelector("ville", is_dual=True, parent_id="")]
        assert compute_tracked_form_keys(selectors) == {"ville"}

    def test_empty_selector_list_returns_empty_set(self) -> None:
        assert compute_tracked_form_keys([]) == set()


# ---------------------------------------------------------------------------
# Cross-helper integration : ensure the rule layers compose
# ---------------------------------------------------------------------------


class TestPipelineComposition:
    """One smoke test that the helpers actually compose : a
    merged-state run through the pipeline gives the same result as
    the orchestrator would. Catches off-by-one shape mismatches
    between merge_form_state_into_filter's output and
    apply_filter_pipeline's input."""

    def test_merge_then_pipeline_e2e(self) -> None:
        secteur = _StubSelector("secteur", tags={"presse": {1, 2}, "media": {3}})
        ville = _StubSelector("ville", tags={"paris": {1, 3}, "lyon": {2}})
        selectors = [secteur, ville]

        state = merge_form_state_into_filter(
            {},
            {"secteur": ["presse"], "ville": ["paris"]},
            tracked_keys=compute_tracked_form_keys(selectors),
        )

        experts = [_expert(id=i) for i in (1, 2, 3)]
        result = apply_filter_pipeline(experts, state, selectors)

        # secteur=presse → {1, 2} ; ∩ ville=paris {1, 3} → {1}
        assert {e.id for e in result} == {1}
