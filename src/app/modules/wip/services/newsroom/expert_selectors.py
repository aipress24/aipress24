# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Expert filtering service for Avis d'Enquête targeting.

Each `BaseSelector` subclass owns one filter dimension (secteur,
métier, langue, …). It contributes (1) the list of options surfaced
in the dropdown, (2) the predicate used to keep / drop experts in
the candidate pool.

Phase 1 of bug #0150 / Annie's ciblage request reshapes the option
source: dropdowns now show the **full KYC taxonomy** (not just values
present in the current expert pool), with each option suffixed by
`(N)` — the number of experts in the candidate pool that match. This
lets a journalist « ratisser plus large » when the database is sparse
and instantly see which criteria would zero out the result set.

Selectors that are not backed by a static taxonomy (département,
ville — derived from country selection) keep their data-driven
behaviour.
"""

from __future__ import annotations

import abc
import unicodedata
from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass
from functools import cached_property

from app.models.auth import User
from app.modules.kyc.field_label import (
    country_code_to_country_name,
    taille_orga_code_to_label,
)
from app.services.taxonomies import get_taxonomy

# Type alias for filter state that can contain:
# - Filter values (list[str]) for selectors like secteur, metier, etc.
# - Expert IDs (list[int]) for selected_experts
FilterState = dict[str, str | list[str] | list[int]]


@dataclass(frozen=True, order=True)
class FilterOption:
    """A selectable filter option.

    `label` is the display text the user sees in the dropdown — it
    includes the `(N)` count badge appended by `BaseSelector`. `id`
    is the raw value used for filtering and DB storage; never enrich
    it. Sort order is by `id` first (default dataclass `order`), but
    `BaseSelector._make_options` re-sorts on a diacritic-stripped
    version of the label-stem (count badge stripped) so the visual
    order is alphabetical regardless of count.
    """

    id: str
    label: str
    selected: str = ""


class BaseSelector(abc.ABC):
    """Base class for ciblage filter selectors.

    Subclasses declare:

    - `id`, `label` — DOM/form id and human-readable section title.
    - `taxonomy_name` — name of the static taxonomy that backs the
      dropdown options. When set, options come from
      `get_taxonomy(taxonomy_name)` and cover the FULL list, not just
      values present in `self._experts`. Set to `None` for
      data-driven selectors (département, ville).
    - `_expert_values(expert)` — extracts the values this expert has
      for this dimension. Used both to compute per-option counts and
      to filter the expert pool.
    """

    id: str
    label: str
    taxonomy_name: str | None = None

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
        return self._make_options(self.get_values())

    def get_values(self) -> set[str]:
        """Available raw values for this selector.

        Default: union of the full taxonomy (when `taxonomy_name` is
        set) and the values currently held by any expert. The union
        guarantees that legacy data entered before a taxonomy change
        is not silently dropped from the list, while still surfacing
        every option an admin can pick today.

        Subclasses with a derived data source (département, ville)
        override this.
        """
        result: set[str] = set()
        if self.taxonomy_name:
            result.update(get_taxonomy(self.taxonomy_name))
        for expert in self._experts:
            result.update(self._expert_values(expert))
        return result

    @abc.abstractmethod
    def _expert_values(self, expert: User) -> Iterable[str]:
        """Return the values this expert has for this selector."""

    def filter_experts(
        self,
        criteria: set[str],
        experts: list[User],
    ) -> list[User]:
        """Default filter: keep experts whose `_expert_values` intersect
        the criteria. Subclasses with non-list semantics override."""
        if not criteria:
            return experts
        return [
            e for e in experts if any(v in criteria for v in self._expert_values(e))
        ]

    @cached_property
    def _count_by_value(self) -> dict[str, int]:
        """Per-value count of matching experts in the candidate pool.

        Lazy on first access so a test that instantiates a selector
        without intending to render options doesn't pay (or trip on)
        the expert profile iteration.
        """
        counter: Counter[str] = Counter()
        for expert in self._experts:
            for value in self._expert_values(expert):
                counter[value] += 1
        return dict(counter)

    def _label_for(self, value: str) -> str:
        """Display label for `value` before the count badge.

        Override for selectors whose raw value is a code (taille,
        pays). Default: value is its own label.
        """
        return value

    def _make_options(self, values: Iterable[str]) -> list[FilterOption]:
        """Build the sorted, count-annotated option list."""
        seen: set[str] = set()
        rows: list[tuple[str, FilterOption]] = []
        for value in values:
            if not value or value in seen:
                continue
            seen.add(value)
            selected = "selected" if value in self.values else ""
            label_text = self._label_for(value)
            count = self._count_by_value.get(value, 0)
            display = f"{label_text} ({count})"
            sort_key = _normalize(label_text)
            rows.append((sort_key, FilterOption(value, display, selected)))
        rows.sort(key=lambda r: r[0])
        return [opt for _, opt in rows]


def _normalize(text: str) -> str:
    """Sort key that ignores diacritics and case."""
    normalized = unicodedata.normalize("NFKD", text)
    return "".join(c for c in normalized if unicodedata.category(c) != "Mn").lower()


# ----------------------------------------------------------------
# Selector Implementations
# ----------------------------------------------------------------


class SecteurSelector(BaseSelector):
    """Filter by sector of activity (detailed level)."""

    id = "secteur"
    label = "Secteur d'activité"
    taxonomy_name = "secteur_detaille"

    def _expert_values(self, expert: User) -> Iterable[str]:
        return expert.profile.secteurs_activite


class TypeEntreprisePresseMediasSelector(BaseSelector):
    id = "type_entreprise_presse_medias"
    label = "Type d'entreprise presse & médias"
    taxonomy_name = "type_entreprises_medias"

    def _expert_values(self, expert: User) -> Iterable[str]:
        return expert.profile.type_entreprise_media


class TypePresseMediasSelector(BaseSelector):
    id = "type_presse_et_media"
    label = "Type presse et médias"
    taxonomy_name = "media_type"

    def _expert_values(self, expert: User) -> Iterable[str]:
        return expert.profile.type_presse_et_media


class LanguesSelector(BaseSelector):
    id = "langues"
    label = "Langues"
    taxonomy_name = "langue"

    def _expert_values(self, expert: User) -> Iterable[str]:
        return expert.profile.langues


class MetierSelector(BaseSelector):
    id = "metier"
    label = "Métier"
    taxonomy_name = "metier"

    def _expert_values(self, expert: User) -> Iterable[str]:
        return expert.tous_metiers


class FonctionSelector(BaseSelector):
    """Aggregate « toutes fonctions » selector across the three families."""

    id = "fonction"
    label = "Toutes fonctions"
    # No single taxonomy backs "toutes fonctions" — it's the union of
    # pol/adm, org-priv, ass/syn. We union the three taxonomies so
    # the dropdown shows every possible function across the platform.
    taxonomy_name = None  # populated below

    def _expert_values(self, expert: User) -> Iterable[str]:
        return expert.profile.toutes_fonctions

    def get_values(self) -> set[str]:
        # Union of the three function taxonomies + values held by
        # current experts. Keeps « toutes fonctions » truly inclusive.
        result: set[str] = set()
        for tx in (
            "profession_fonction_public",
            "profession_fonction_prive",
            "profession_fonction_asso",
        ):
            result.update(get_taxonomy(tx))
        for expert in self._experts:
            result.update(self._expert_values(expert))
        return result


class FonctionJournalismeSelector(BaseSelector):
    id = "fonction_journalisme"
    label = "Fonctions du journalisme"
    taxonomy_name = "journalisme_fonction"

    def _expert_values(self, expert: User) -> Iterable[str]:
        return expert.profile.fonctions_journalisme


class FonctionPolitiquesAdministrativesSelector(BaseSelector):
    id = "fonction_pol_adm"
    label = "Fonctions politiques et administratives"
    taxonomy_name = "profession_fonction_public"

    def _expert_values(self, expert: User) -> Iterable[str]:
        return expert.profile.fonctions_pol_adm_detail


class FonctionOrganisationsPriveesSelector(BaseSelector):
    id = "fonction_org_priv"
    label = "Fonctions organisations privées"
    taxonomy_name = "profession_fonction_prive"

    def _expert_values(self, expert: User) -> Iterable[str]:
        return expert.profile.fonctions_org_priv_detail


class FonctionAssociationsSyndicatsSelector(BaseSelector):
    id = "fonction_ass_syn"
    label = "Fonctions associations et syndicats"
    taxonomy_name = "profession_fonction_asso"

    def _expert_values(self, expert: User) -> Iterable[str]:
        return expert.profile.fonctions_ass_syn_detail


class CompetencesGeneralesSelector(BaseSelector):
    id = "competences"
    label = "Compétences générales"
    taxonomy_name = "competence_expert"

    def _expert_values(self, expert: User) -> Iterable[str]:
        return expert.profile.competences


class CompetencesJournalismeSelector(BaseSelector):
    id = "competences_journalisme"
    label = "Compétences journalisme"
    taxonomy_name = "journalisme_competence"

    def _expert_values(self, expert: User) -> Iterable[str]:
        return expert.profile.competences_journalisme


class TypeOrganisationSelector(BaseSelector):
    id = "type_organisation"
    label = "Type d'organisation"
    taxonomy_name = "type_organisation_detail"

    def _expert_values(self, expert: User) -> Iterable[str]:
        return expert.profile.type_organisation


class TailleOrganisationSelector(BaseSelector):
    id = "taille_organisation"
    label = "Taille de l'organisation"
    taxonomy_name = "taille_organisation"

    def _expert_values(self, expert: User) -> Iterable[str]:
        return expert.profile.taille_organisation

    def _label_for(self, value: str) -> str:
        return taille_orga_code_to_label(value)


class PaysSelector(BaseSelector):
    """Filter by country.

    Backed by the `pays` taxonomy but the country code stored on a
    profile is a single string, not a list — so `_expert_values`
    wraps it in a single-element list and `filter_experts` is
    overridden to compare on equality.
    """

    id = "pays"
    label = "Pays"
    taxonomy_name = "pays"

    def _expert_values(self, expert: User) -> Iterable[str]:
        country = expert.profile.country
        return [country] if country else []

    def filter_experts(
        self,
        criteria: set[str],
        experts: list[User],
    ) -> list[User]:
        if not criteria:
            return experts
        return [e for e in experts if e.profile.country in criteria]

    def _label_for(self, value: str) -> str:
        return country_code_to_country_name(value)


class DepartementSelector(BaseSelector):
    """Filter by department.

    Data-driven (no fixed taxonomy): the list of departments shown
    depends on which countries are currently selected. Kept narrow on
    purpose — listing all FR + intl departments would explode the
    dropdown.
    """

    id = "departement"
    label = "Département"
    taxonomy_name = None

    def _expert_values(self, expert: User) -> Iterable[str]:
        dep = expert.profile.departement
        return [dep] if dep else []

    def get_values(self) -> set[str]:
        selected_countries = self._state.get("pays")
        if not selected_countries:
            return set()
        if isinstance(selected_countries, str):
            country_criteria: set[str] = {selected_countries}
        else:
            country_criteria = {str(v) for v in selected_countries}
        return {
            u.profile.departement
            for u in self._experts
            if u.profile.country in country_criteria and u.profile.departement
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
    """Filter by city — derived from selected departments."""

    id = "ville"
    label = "Ville"
    taxonomy_name = None

    def _expert_values(self, expert: User) -> Iterable[str]:
        ville = expert.profile.ville
        return [ville] if ville else []

    def get_values(self) -> set[str]:
        selected_departements = self._state.get("departement")
        if not selected_departements:
            return set()
        if isinstance(selected_departements, str):
            departement_criteria: set[str] = {selected_departements}
        else:
            departement_criteria = {str(v) for v in selected_departements}
        return {
            u.profile.ville
            for u in self._experts
            if u.profile.departement in departement_criteria and u.profile.ville
        }

    def filter_experts(
        self,
        criteria: set[str],
        experts: list[User],
    ) -> list[User]:
        if not criteria:
            return experts
        return [e for e in experts if e.profile.ville in criteria]
