# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Expert filtering service for Avis d'Enquête targeting."""

from __future__ import annotations

from collections.abc import Generator
from typing import cast

from flask import request
from svcs.flask import container

from app.models.auth import User
from app.models.repositories import UserRepository
from app.services.sessions import SessionService

# FilterState : Type alias for filter state that can contain:
# - Filter values (list[str]) for selectors like secteur, metier, etc.
# - Expert IDs (list[int]) for selected_experts
#
from .expert_selectors import (
    BaseSelector,
    DepartementSelector,
    FilterState,
    FonctionSelector,
    MetierSelector,
    PaysSelector,
    SecteurSelector,
    TailleOrganisationSelector,
    TypeOrganisationSelector,
    VilleSelector,
)

MAX_SELECTABLE_EXPERTS = 50


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

    def __init__(self) -> None:
        self._session = container.get(SessionService)
        self._session_key: str = ""
        self._user_repo = container.get(UserRepository)
        self._state: FilterState = {}
        self._all_experts: list[User] | None = None
        self._selectors: list[BaseSelector] | None = None

    # ----------------------------------------------------------------
    # Public API
    # ----------------------------------------------------------------

    def initialize(self, avis_enquete_id: str) -> None:
        """Initialize filter state from avis_enquete_id, session and request."""
        self._set_session_key(avis_enquete_id)
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
        selectors = self._get_selectors()
        experts = self._get_all_experts()

        # If no filters applied, return all (limited)
        if all(not self._state.get(s.id) for s in selectors):
            return experts[:MAX_SELECTABLE_EXPERTS]

        # Apply each selector's filter
        for selector in selectors:
            selected_values = self._state.get(selector.id)
            if not selected_values:
                continue
            criteria = (
                set(selected_values)
                if isinstance(selected_values, list)
                else {selected_values}
            )
            experts = selector.filter_experts(criteria, experts)

        # Exclude already-selected experts
        selected_ids = set(self._state.get("selected_experts", []))
        new_experts = [e for e in experts if e.id not in selected_ids]

        new_experts.sort(key=lambda e: (e.last_name, e.first_name))
        return new_experts[:MAX_SELECTABLE_EXPERTS]

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
        expert_ids = list(self._get_expert_ids_from_request())
        existing = self._state.get("selected_experts", [])
        if isinstance(existing, list):
            # selected_experts always contains int IDs
            for item in existing:
                if isinstance(item, int):
                    expert_ids.append(item)
        self._state["selected_experts"] = list(set(expert_ids))

    def update_experts_from_request(self) -> None:
        """Replace current selection with experts from form."""
        expert_ids = list(self._get_expert_ids_from_request())
        self._state["selected_experts"] = expert_ids

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

    def get_action_from_request(self) -> str:
        """
        Extract action from form data.

        Returns:
            Action name (e.g., "confirm", "update", "add") or empty string
        """
        for name in request.form.to_dict():
            if name.startswith("action:"):
                return name.split(":")[1]
        return ""

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

        selector_keys = {s.id for s in self._get_selectors()}
        seen_selectors: set[str] = set()

        for key, values in selector_data.items():
            if key in selector_keys:
                actual_values = [v for v in values if v]
                if actual_values:
                    self._state[key] = actual_values
                    seen_selectors.add(key)

        # Clear unmentioned selectors
        for key in selector_keys:
            if key not in seen_selectors:
                self._state.pop(key, None)

    def _get_expert_ids_from_request(self) -> Generator[int, None, None]:
        """Extract expert IDs from form data."""
        form_data = request.form.to_dict()
        for k in form_data:
            if k.startswith("expert:"):
                yield int(k.split(":")[1])

    def _get_all_experts(self) -> list[User]:
        """Get all experts (cached)."""
        if self._all_experts is None:
            self._all_experts = self._user_repo.list()
        return self._all_experts

    def _get_selectors(self) -> list[BaseSelector]:
        """Get all selectors (cached)."""
        if self._selectors is None:
            experts = self._get_all_experts()
            self._selectors = [
                SecteurSelector(self._state, experts),
                MetierSelector(self._state, experts),
                FonctionSelector(self._state, experts),
                # TypeEntreprisePresseMediasSelector(self._state, experts),
                TypeOrganisationSelector(self._state, experts),
                TailleOrganisationSelector(self._state, experts),
                PaysSelector(self._state, experts),
                DepartementSelector(self._state, experts),
                VilleSelector(self._state, experts),
            ]
        return self._selectors
