# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Expert filtering service for Avis d'Enquête targeting."""

from __future__ import annotations

import abc
import unicodedata
from dataclasses import dataclass

from app.models.auth import User
from app.modules.kyc.field_label import (
    country_code_to_country_name,
    taille_orga_code_to_label,
)

# Type alias for filter state that can contain:
# - Filter values (list[str]) for selectors like secteur, metier, etc.
# - Expert IDs (list[int]) for selected_experts
FilterState = dict[str, str | list[str] | list[int]]

MAX_OPTIONS = 100


@dataclass(frozen=True, order=True)
class FilterOption:
    """A selectable filter option."""

    id: str
    label: str
    selected: str = ""


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


class TypeEntreprisePresseMediasSelector(BaseSelector):
    """Filter by Type d'entreprise presse & médias."""

    id = "type_entreprise_presse_medias"
    label = "Type d'entreprise presse & médias"

    def get_values(self) -> set[str]:
        merged: set[str] = set()
        for expert in self._experts:
            merged.update(expert.profile.type_entreprise_media)
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
            if any(x in criteria for x in e.profile.type_entreprise_media)
        ]


class TypePresseMediasSelector(BaseSelector):
    """Filter by Type of presse & médias."""

    id = "type_presse_et_media"
    label = "Type presse et médias"

    def get_values(self) -> set[str]:
        merged: set[str] = set()
        for expert in self._experts:
            merged.update(expert.profile.type_presse_et_media)
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
            if any(x in criteria for x in e.profile.type_presse_et_media)
        ]


class LanguesSelector(BaseSelector):
    """Filter by Type of presse & médias."""

    id = "langues"
    label = "Langues"

    def get_values(self) -> set[str]:
        merged: set[str] = set()
        for expert in self._experts:
            merged.update(expert.profile.langues)
        return merged

    def filter_experts(
        self,
        criteria: set[str],
        experts: list[User],
    ) -> list[User]:
        if not criteria:
            return experts
        return [e for e in experts if any(x in criteria for x in e.profile.langues)]


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
