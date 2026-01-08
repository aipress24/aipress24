# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Expert filtering service for Avis d'Enquête targeting."""

from __future__ import annotations

import abc
import unicodedata
from collections.abc import Generator
from dataclasses import dataclass

from flask import request
from svcs.flask import container

from app.models.auth import User
from app.models.repositories import UserRepository
from app.modules.kyc.field_label import (
    country_code_to_country_name,
    taille_orga_code_to_label,
)
from app.services.sessions import SessionService

# Type alias for filter state that can contain:
# - Filter values (list[str]) for selectors like secteur, metier, etc.
# - Expert IDs (list[int]) for selected_experts
FilterState = dict[str, str | list[str] | list[int]]

MAX_SELECTABLE_EXPERTS = 50
MAX_OPTIONS = 100


@dataclass(frozen=True, order=True)
class FilterOption:
    """A selectable filter option."""

    id: str
    label: str
    selected: str = ""


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

    def __init__(self, avis_enquete_id: int | str) -> None:
        self.avis_enquete_id = avis_enquete_id
        self.session_key = f"newsroom:ciblage:{self.avis_enquete_id}"
        self._session = container.get(SessionService)
        self._user_repo = container.get(UserRepository)
        self._state: FilterState = {}
        self._all_experts: list[User] | None = None
        self._selectors: list[BaseSelector] | None = None

    # ----------------------------------------------------------------
    # Public API
    # ----------------------------------------------------------------

    def initialize(self) -> None:
        """Initialize filter state from session and request."""
        self._restore_state()
        self._update_state_from_request()

    def save_state(self) -> None:
        """Persist filter state to session."""
        self._session[self.session_key] = self._state

    def clear_state(self) -> None:
        """Clear filter state from session."""
        self._state = {}
        self._session[self.session_key] = {}

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

    def _restore_state(self) -> None:
        """Restore state from session."""
        self._state = self._session.get(self.session_key, {})

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

        for k, values in selector_data.items():
            if k in selector_keys:
                clean_values = [v for v in values if v]
                if clean_values:
                    self._state[k] = clean_values
                    seen_selectors.add(k)

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
                TypeOrganisationSelector(self._state, experts),
                TailleOrganisationSelector(self._state, experts),
                PaysSelector(self._state, experts),
                DepartementSelector(self._state, experts),
                VilleSelector(self._state, experts),
            ]
        return self._selectors


# ----------------------------------------------------------------
# Selector Base Class
# ----------------------------------------------------------------


class BaseSelector(abc.ABC):
    """
    Base class for expert filter selectors.

    Each selector filters experts by a specific criterion
    (e.g., sector, location, organization type).
    """

    id: str
    label: str

    def __init__(
        self,
        state: FilterState,
        experts: list[User],
    ) -> None:
        self._state = state
        self._experts = experts
        raw_values = state.get(self.id, [])
        # Selectors only use string filter values, not int expert IDs
        if isinstance(raw_values, list):
            self.values = {str(v) for v in raw_values}
        elif raw_values:
            self.values = {str(raw_values)}
        else:
            self.values = set()

    @property
    def options(self) -> list[FilterOption]:
        """Get available options for this selector."""
        choice_values = self.get_values()
        return self._make_options(choice_values)[:MAX_OPTIONS]

    @abc.abstractmethod
    def get_values(self) -> set[str]:
        """Get available values for this selector."""

    @abc.abstractmethod
    def filter_experts(
        self,
        criteria: set[str],
        experts: list[User],
    ) -> list[User]:
        """Filter experts by criteria."""

    def _make_options(self, values: set[str]) -> list[FilterOption]:
        """Convert values to FilterOption list."""
        options: set[FilterOption] = set()
        for value in values:
            selected = "selected" if value in self.values else ""
            option = FilterOption(value, value, selected)
            options.add(option)
        return sorted(options, key=self._sorter)

    def _sorter(self, option: FilterOption) -> str:
        """Sort key that ignores diacritics."""
        normalized = unicodedata.normalize("NFKD", option.label)
        return "".join(c for c in normalized if unicodedata.category(c) != "Mn")


# ----------------------------------------------------------------
# Selector Implementations
# ----------------------------------------------------------------


class SecteurSelector(BaseSelector):
    """Filter by sector of activity."""

    id = "secteur"
    label = "Secteur d'activité"

    def get_values(self) -> set[str]:
        merged: set[str] = set()
        for expert in self._experts:
            merged.update(expert.profile.secteurs_activite)
        return merged

    def filter_experts(
        self,
        criteria: set[str],
        experts: list[User],
    ) -> list[User]:
        if not criteria:
            return experts
        return [
            e
            for e in experts
            if any(x in criteria for x in e.profile.secteurs_activite)
        ]


class MetierSelector(BaseSelector):
    """Filter by profession/trade."""

    id = "metier"
    label = "Métier"

    def get_values(self) -> set[str]:
        merged: set[str] = set()
        for expert in self._experts:
            merged.update(expert.tous_metiers)
        return merged

    def filter_experts(
        self,
        criteria: set[str],
        experts: list[User],
    ) -> list[User]:
        if not criteria:
            return experts
        return [e for e in experts if any(x in criteria for x in e.tous_metiers)]


class FonctionSelector(BaseSelector):
    """Filter by job function."""

    id = "fonction"
    label = "Fonction"

    def get_values(self) -> set[str]:
        merged: set[str] = set()
        for expert in self._experts:
            merged.update(expert.profile.toutes_fonctions)
        return merged

    def filter_experts(
        self,
        criteria: set[str],
        experts: list[User],
    ) -> list[User]:
        if not criteria:
            return experts
        return [
            e for e in experts if any(x in criteria for x in e.profile.toutes_fonctions)
        ]


class TypeOrganisationSelector(BaseSelector):
    """Filter by organization type."""

    id = "type_organisation"
    label = "Type d'organisation"

    def get_values(self) -> set[str]:
        merged: set[str] = set()
        for expert in self._experts:
            merged.update(expert.profile.type_organisation)
        return merged

    def filter_experts(
        self,
        criteria: set[str],
        experts: list[User],
    ) -> list[User]:
        if not criteria:
            return experts
        return [
            e
            for e in experts
            if any(x in criteria for x in e.profile.type_organisation)
        ]


class TailleOrganisationSelector(BaseSelector):
    """Filter by organization size."""

    id = "taille_organisation"
    label = "Taille de l'organisation"

    def get_values(self) -> set[str]:
        merged: set[str] = set()
        for expert in self._experts:
            merged.update(expert.profile.taille_organisation)
        return merged

    def filter_experts(
        self,
        criteria: set[str],
        experts: list[User],
    ) -> list[User]:
        if not criteria:
            return experts
        return [
            e
            for e in experts
            if any(x in criteria for x in e.profile.taille_organisation)
        ]

    def _make_options(self, values: set[str]) -> list[FilterOption]:
        options: set[FilterOption] = set()
        for value in values:
            selected = "selected" if value in self.values else ""
            label = taille_orga_code_to_label(value)
            option = FilterOption(value, label, selected)
            options.add(option)
        return sorted(options)


class PaysSelector(BaseSelector):
    """Filter by country."""

    id = "pays"
    label = "Pays"

    def get_values(self) -> set[str]:
        return {e.profile.country for e in self._experts}

    def filter_experts(
        self,
        criteria: set[str],
        experts: list[User],
    ) -> list[User]:
        if not criteria:
            return experts
        return [e for e in experts if e.profile.country in criteria]

    def _make_options(self, values: set[str]) -> list[FilterOption]:
        options: set[FilterOption] = set()
        for value in values:
            selected = "selected" if value in self.values else ""
            label = country_code_to_country_name(value)
            option = FilterOption(value, label, selected)
            options.add(option)
        return sorted(options, key=self._sorter)


class DepartementSelector(BaseSelector):
    """Filter by department (French administrative division)."""

    id = "departement"
    label = "Département"

    def get_values(self) -> set[str]:
        selected_countries = self._state.get("pays")
        if not selected_countries:
            return set()
        if isinstance(selected_countries, str):
            country_criteria = {selected_countries}
        else:
            country_criteria = set(selected_countries)
        return {
            u.profile.departement
            for u in self._experts
            if u.profile.country in country_criteria
        }

    def filter_experts(
        self,
        criteria: set[str],
        experts: list[User],
    ) -> list[User]:
        if not criteria:
            return experts
        return [e for e in experts if e.profile.departement in criteria]


class VilleSelector(BaseSelector):
    """Filter by city."""

    id = "ville"
    label = "Ville"

    def get_values(self) -> set[str]:
        selected_departements = self._state.get("departement")
        if not selected_departements:
            return set()
        if isinstance(selected_departements, str):
            departement_criteria = {selected_departements}
        else:
            departement_criteria = set(selected_departements)
        return {
            u.profile.ville
            for u in self._experts
            if u.profile.departement in departement_criteria
        }

    def filter_experts(
        self,
        criteria: set[str],
        experts: list[User],
    ) -> list[User]:
        if not criteria:
            return experts
        return [e for e in experts if e.profile.ville in criteria]
