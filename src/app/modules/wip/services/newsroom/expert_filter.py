# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Expert filtering service for Avis d'Enquête targeting."""

from __future__ import annotations

from collections.abc import Generator, Iterable
from dataclasses import dataclass
from typing import cast

from flask import request
from svcs.flask import container

from app.models.auth import User
from app.models.repositories import UserRepository
from app.services.sessions import SessionService

# FilterState : Type alias for filter state that can contain:
# - Filter values (list[str]) for selectors like secteur, metier, etc.
# - Expert IDs (list[int]) for selected_experts
from .expert_selectors import (
    BaseSelector,
    CompetencesGeneralesSelector,
    CompetencesJournalismeSelector,
    DepartementSelector,
    FilterState,
    FonctionAssociationsSyndicatsSelector,
    FonctionJournalismeSelector,
    FonctionOrganisationsPriveesSelector,
    FonctionPolitiquesAdministrativesSelector,
    FonctionSelector,
    LanguesSelector,
    MetierSelector,
    PaysSelector,
    SecteurSelector,
    TailleOrganisationSelector,
    TypeEntreprisePresseMediasSelector,
    TypeOrganisationSelector,
    TypePresseMediasSelector,
    VilleSelector,
)

MAX_SELECTABLE_EXPERTS = 50


@dataclass(frozen=True)
class SelectorSection:
    """A titled group of selectors rendered in the ciblage UI.

    Phase 2 of bug #0150 (Annie's ciblage request): the journalist
    asked for the dropdowns to be grouped under 4 thematic headings
    instead of an undifferentiated 2-column grid of 17 items. Sections
    are pure UI metadata — the underlying selectors and filter
    pipeline are unchanged.
    """

    title: str
    selectors: list[BaseSelector]


# ── Pure decision helpers ───────────────────────────────────────────
#
# `ExpertFilterService` is a stateful Flask-coupled orchestrator
# (request, session, repository). The genuinely pure pieces — filter
# pipeline, form-state merging, selection dedup, form parsing,
# section grouping — are factored out so the rules can be unit-tested
# without a Flask context, an HTMX request shape, or a DB. The class
# delegates to these for every decision.


def apply_filter_pipeline(
    experts: list[User],
    state: FilterState,
    selectors: list[BaseSelector],
    *,
    max_count: int = MAX_SELECTABLE_EXPERTS,
) -> list[User]:
    """Run the targeted-experts pipeline. Pure — no DB, no request.

    Rules :

    1. If no selector has any criterion set in ``state``, return the
       first ``max_count`` experts without filtering, sorting, or
       exclusion — this matches the « no filters » view the journalist
       sees on first open.
    2. Otherwise, AND every active selector's filter together over
       the candidate pool.
    3. Exclude experts whose id appears in ``state["selected_experts"]``
       (the « already picked » list) — they show up in a separate
       section of the UI.
    4. Sort by (last_name, first_name) so the table is alphabetical.
    5. Cap at ``max_count`` — the UI table has no pagination ;
       beyond 50 the journalist is told to refine.
    """
    if all(not state.get(s.id) for s in selectors):
        return experts[:max_count]

    filtered = experts
    for selector in selectors:
        selected_values = state.get(selector.id)
        if not selected_values:
            continue
        criteria: set[str] = (
            set(selected_values)
            if isinstance(selected_values, list)
            else {selected_values}
        )
        filtered = selector.filter_experts(criteria, filtered)

    selected_ids = set(state.get("selected_experts", []))
    new_experts = [e for e in filtered if e.id not in selected_ids]
    new_experts.sort(key=lambda e: (e.last_name, e.first_name))
    return new_experts[:max_count]


def merge_form_state_into_filter(
    state: FilterState,
    form_lists: dict[str, list[str]],
    tracked_keys: set[str],
) -> FilterState:
    """Apply an HTMX selector-change form payload to the filter state.

    Pure — returns a NEW state dict, doesn't mutate the input.

    Two rules :

    * Every tracked key (selector id OR dual-selector parent id) found
      with non-empty values is written into the state.
    * Every tracked key NOT mentioned in the payload is popped — that
      models « user unchecked the dropdown ». Without this drop, stale
      criteria leak across HTMX re-renders.

    Non-tracked keys in the payload (e.g. ``selector_change`` itself,
    CSRF tokens) are ignored — the form has many fields that don't
    belong to a selector.
    """
    new_state: FilterState = dict(state)
    seen_keys: set[str] = set()
    for key, values in form_lists.items():
        if key not in tracked_keys:
            continue
        actual = [v for v in values if v]
        if actual:
            new_state[key] = actual
            seen_keys.add(key)

    for key in tracked_keys:
        if key not in seen_keys:
            new_state.pop(key, None)
    return new_state


def merge_expert_selection(existing: object, new_ids: list[int]) -> list[int]:
    """Combine the previously-selected expert ids with a fresh batch
    from the form. Pure — order is not preserved (the UI sorts later).

    Tolerant of legacy state shapes : ``existing`` may be the
    int-typed list we expect, or it may have been overwritten by an
    inconsistent caller. Anything that isn't a list of ints is
    silently dropped — the user re-checks any ids they care about
    via the form."""
    out: list[int] = list(new_ids)
    if isinstance(existing, list):
        for item in existing:
            if isinstance(item, int):
                out.append(item)
    return list(set(out))


def parse_action_from_form(form_keys: Iterable[str]) -> str:
    """Extract the form's action name. Pure.

    The form encodes the user's click as a key like ``action:confirm``
    or ``action:update`` (so a single ``<form>`` can dispatch multiple
    actions without JavaScript). Returns the suffix or ``""`` if no
    action key is present.

    ``form_keys`` is anything iterable producing the form's keys —
    a dict, a list, ``request.form.to_dict()``."""
    for key in form_keys:
        if isinstance(key, str) and key.startswith("action:"):
            return key.split(":", 1)[1]
    return ""


def parse_expert_ids_from_form(form_keys: Iterable[str]) -> list[int]:
    """Extract expert ids from form keys shaped ``expert:<int>``. Pure.

    The form uses keys like ``expert:42`` so the journalist can
    toggle multiple experts in a single submit. Non-numeric suffixes
    raise — that's an input-shape bug worth surfacing, not a silent
    drop."""
    out: list[int] = []
    for key in form_keys:
        if isinstance(key, str) and key.startswith("expert:"):
            out.append(int(key.split(":", 1)[1]))
    return out


def build_sections_from_selectors(
    selectors: list[BaseSelector],
) -> list[SelectorSection]:
    """Group the 17 selectors into Annie's 4 thematic headings
    (bug #0150 phase 2). Pure — operates only on the selector list."""
    by_id = {s.id: s for s in selectors}

    def pick(*ids: str) -> list[BaseSelector]:
        return [by_id[i] for i in ids if i in by_id]

    return [
        SelectorSection(
            title="Secteurs d'activité et types d'organisation",
            selectors=pick(
                "secteur",
                "type_organisation",
                "type_entreprise_presse_medias",
                "type_presse_et_media",
                "taille_organisation",
            ),
        ),
        SelectorSection(
            title="Géolocalisation",
            selectors=pick("pays", "departement", "ville"),
        ),
        SelectorSection(
            title="Fonctions",
            selectors=pick(
                "fonction_pol_adm",
                "fonction_org_priv",
                "fonction_ass_syn",
                "fonction",
                "fonction_journalisme",
            ),
        ),
        SelectorSection(
            title="Métiers, compétences & langues",
            selectors=pick(
                "metier",
                "competences",
                "competences_journalisme",
                "langues",
            ),
        ),
    ]


def compute_tracked_form_keys(selectors: list[BaseSelector]) -> set[str]:
    """Return the set of form keys ``merge_form_state_into_filter``
    should pay attention to : every selector id, plus the parent_id
    of any dual selector (parent dropdowns don't filter experts but
    must round-trip through state for the cascade UI). Pure."""
    selector_keys = {s.id for s in selectors}
    parent_keys = {
        getattr(s, "parent_id", "") for s in selectors if getattr(s, "is_dual", False)
    }
    parent_keys.discard("")
    return selector_keys | parent_keys


class ExpertFilterService:
    """
    Service for filtering experts based on multiple criteria.

    Manages:
    - Filter state (stored in session)
    - Available filter options
    - Expert filtering and selection

    Usage:
        service = ExpertFilterService()
        service.initialize()
        experts = service.get_selectable_experts()
        # ... user makes selections ...
        service.add_experts_from_request()
        service.save_state()
    """

    def __init__(
        self,
        session: SessionService | None = None,
        user_repo: UserRepository | None = None,
    ) -> None:
        # `session` / `user_repo` are injectable — production leaves them
        # None and resolves the real services from the container ; tests
        # pass stubs (a dict for the session store, a fake repo) so they
        # don't have to patch the DI container.
        self._session = session if session is not None else container.get(SessionService)
        self._session_key: str = ""
        self._user_repo = (
            user_repo if user_repo is not None else container.get(UserRepository)
        )
        self._state: FilterState = {}
        self._all_experts: list[User] | None = None
        self._selectors: list[BaseSelector] | None = None
        self._avis_enquete = None

    # ----------------------------------------------------------------
    # Public API
    # ----------------------------------------------------------------

    def initialize(self, avis_enquete_id: str, avis_enquete=None) -> None:
        """Initialize filter state from avis_enquete_id, session and request.

        When `avis_enquete` is provided, the candidate pool is pre-scoped to
        experts with a thematic match and recent activity (MVP matchmaking).
        """
        self._set_session_key(avis_enquete_id)
        self._avis_enquete = avis_enquete
        self._restore_state()
        self._update_state_from_request()

    def save_state(self) -> None:
        """Persist filter state to session."""
        self._session[self._session_key] = self._state

    def clear_state(self) -> None:
        """Clear filter state from session."""
        self._state = {}
        self.save_state()

    def get_selectable_experts(self) -> list[User]:
        """
        Get experts matching current filter criteria.

        Returns:
            List of experts (limited to MAX_SELECTABLE_EXPERTS)
        """
        return apply_filter_pipeline(
            self._get_all_experts(), self._state, self._get_selectors()
        )

    def get_selected_experts(self) -> list[User]:
        """
        Get currently selected experts.

        Returns:
            List of selected User entities
        """
        selected_ids = set(self._state.get("selected_experts", []))
        experts = self._get_all_experts()
        return [e for e in experts if e.id in selected_ids]

    def add_experts_from_request(self) -> None:
        """Add experts from form to current selection."""
        new_ids = parse_expert_ids_from_form(request.form.to_dict())
        self._state["selected_experts"] = merge_expert_selection(
            self._state.get("selected_experts", []), new_ids
        )

    def update_experts_from_request(self) -> None:
        """Replace current selection with experts from form."""
        self._state["selected_experts"] = parse_expert_ids_from_form(
            request.form.to_dict()
        )

    def get_selectors(self) -> list[BaseSelector]:
        """
        Get all available filter selectors.

        Returns:
            List of selector instances
        """
        return self._get_selectors()

    @property
    def selectors(self) -> list[BaseSelector]:
        """Property alias for get_selectors() for template compatibility."""
        return self._get_selectors()

    @property
    def sections(self) -> list[SelectorSection]:
        """Selectors grouped into Annie's 4 thematic sections.

        Order and titles follow the spec from bug #0150. A flat
        `.selectors` view is still exposed for callers that don't
        care about grouping (e.g. validation, state plumbing).
        """
        return build_sections_from_selectors(self._get_selectors())

    def get_action_from_request(self) -> str:
        """
        Extract action from form data.

        Returns:
            Action name (e.g., "confirm", "update", "add") or empty string
        """
        return parse_action_from_form(request.form.to_dict())

    @property
    def state(self) -> FilterState:
        """Current filter state (read-only access)."""
        return self._state

    # ----------------------------------------------------------------
    # Private Methods
    # ----------------------------------------------------------------

    def _set_session_key(self, avis_enquete_id: str) -> None:
        """Set session key for a specific Avis d' Enquête"""
        self._session_key = f"newsroom:ciblage{avis_enquete_id}"

    def _restore_state(self) -> None:
        """Restore state from session."""
        self._state = cast(FilterState, self._session.get(self._session_key, {}))

    def _update_state_from_request(self) -> None:
        """Update state from HTMX request data."""
        if not request.headers.get("HX-Request"):
            return

        data_source = request.args if request.method == "GET" else request.form
        selector_data = dict(data_source.lists())

        if "selector_change" not in selector_data:
            return

        tracked_keys = compute_tracked_form_keys(self._get_selectors())
        self._state = merge_form_state_into_filter(
            self._state, selector_data, tracked_keys
        )

    def _get_expert_ids_from_request(self) -> Generator[int]:
        """Extract expert IDs from form data."""
        yield from parse_expert_ids_from_form(request.form.to_dict())

    def _get_all_experts(self) -> list[User]:
        """Get all experts (cached).

        When an `AvisEnquete` is set on the service (via `initialize`),
        the candidate pool is first pre-scoped with the MVP matchmaking
        pre-filter (thematic match + recent activity).
        """
        if self._all_experts is None:
            experts = self._user_repo.list(active=True)
            if self._avis_enquete is not None:
                from app.modules.wip.services.newsroom.avis_matching import (
                    match_experts_to_avis,
                )

                experts = match_experts_to_avis(experts, self._avis_enquete)
            self._all_experts = experts
        return self._all_experts

    def _get_selectors(self) -> list[BaseSelector]:
        """Get all selectors (cached)."""
        if self._selectors is None:
            experts = self._get_all_experts()
            self._selectors = [
                SecteurSelector(self._state, experts),
                MetierSelector(self._state, experts),
                FonctionSelector(self._state, experts),
                FonctionPolitiquesAdministrativesSelector(self._state, experts),
                FonctionOrganisationsPriveesSelector(self._state, experts),
                FonctionAssociationsSyndicatsSelector(self._state, experts),
                FonctionJournalismeSelector(self._state, experts),
                CompetencesGeneralesSelector(self._state, experts),
                CompetencesJournalismeSelector(self._state, experts),
                TypeEntreprisePresseMediasSelector(self._state, experts),
                TypePresseMediasSelector(self._state, experts),
                TypeOrganisationSelector(self._state, experts),
                TailleOrganisationSelector(self._state, experts),
                LanguesSelector(self._state, experts),
                PaysSelector(self._state, experts),
                DepartementSelector(self._state, experts),
                VilleSelector(self._state, experts),
            ]
        return self._selectors
