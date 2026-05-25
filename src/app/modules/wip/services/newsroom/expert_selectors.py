# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Expert filtering service for Avis d'Enquête targeting.

Each `BaseSelector` subclass owns one filter dimension (secteur,
métier, langue, …). It contributes (1) the list of options surfaced
in the dropdown, (2) the predicate used to keep / drop experts in
the candidate pool.

Bug #0150 / Annie's ciblage request — option source:

- Options come from the union of (KYC taxonomy ∪ values held by
  experts ∪ values the user has already selected).
- Only options matched by ≥ 1 expert in the current candidate pool
  appear in the dropdown — the user explicitly asked for this after
  the first cut: a criterion that immediately empties the result
  set is frustrating noise.
- Currently-selected values are preserved across HTMX re-renders
  even if their count drops to 0 (otherwise the user's own chips
  would vanish mid-edit).
- Each option's label carries a `(N)` suffix so the user sees the
  remaining headroom before committing.

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
from app.modules.kyc.lib.dual_select_multi import convert_dual_choices_js
from app.services.taxonomies import get_taxonomy, get_taxonomy_dual_select

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
    # Phase 3 of bug #0150: subclasses set this to True when they
    # render via the dual-select (parent / child) cascade widget.
    is_dual: bool = False

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

        Default: union of (a) the full taxonomy (when `taxonomy_name`
        is set), (b) values currently held by any expert, and (c)
        values the user has already selected. (a)+(b) supports legacy
        rows whose values fell out of the taxonomy; (c) ensures a
        chip the user typed never disappears mid-flight when an HTMX
        re-render narrows the candidate pool.

        Subclasses with a derived data source (département, ville)
        override this.
        """
        result: set[str] = set(self.values)
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
        """Build the sorted, count-annotated option list.

        Options with zero matching experts are filtered out: the rule
        Annie asked for after seeing the first cut — selecting a
        criterion that immediately produces an empty result set is
        frustrating, so taxonomy entries that aren't held by any
        expert in the current candidate pool simply don't appear.

        A *currently-selected* value is kept even at count 0 so the
        UI never silently drops a chip the user can see; otherwise an
        HTMX re-render after a parent change would erase the user's
        own picks.
        """
        seen: set[str] = set()
        rows: list[tuple[str, FilterOption]] = []
        for value in values:
            if not value or value in seen:
                continue
            seen.add(value)
            count = self._count_by_value.get(value, 0)
            is_selected = value in self.values
            if count == 0 and not is_selected:
                continue
            label_text = self._label_for(value)
            selected = "selected" if is_selected else ""
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
# Dual-select cascade (parent → child) base class
# ----------------------------------------------------------------


class DualSelector(BaseSelector):
    """Two-level cascade selector (parent category → detail).

    Reuses the KYC `dual_select_multi.j2` widget shape so the same
    Alpine/TomSelect choreography (already fixed for bug #0119) keeps
    powering the cascade — no new JS to debug. Annie's explicit
    warning « les sélecteurs sur 2 niveaux, il faut que ça marche! »
    is the reason we don't roll our own.

    Contract:
    - `id` / `label` (inherited) — the *child* / detail field, the
      one that actually feeds the filter pipeline.
    - `parent_id` / `parent_label` — the parent dropdown that narrows
      the child list. Its state is tracked in `FilterState` but it
      isn't a filter criterion by itself (we don't store parent
      values on expert profiles for these taxonomies).
    - `taxonomy_name` — a *multidual* ontology name. Pulled via
      `get_taxonomy_dual_select(name)` to feed the cascade.
    - Detail values are qualified « Parent / Child » — same shape
      KYC stores on profiles, so filtering works directly on the
      profile's detail list.

    Exposes the same shape as `wtforms` so the existing KYC
    `dual_select_multi.j2` template can be reused with `selector` in
    place of `field` (see the ciblage template's `render_dual_selector`
    macro).
    """

    is_dual: bool = True
    parent_id: str
    parent_label: str

    # --- WTForms-like attributes consumed by dual_select_multi.j2 ---

    @property
    def name(self) -> str:
        # The parent dropdown's HTML name (= form key for parent state).
        return self.parent_id

    @property
    def name2(self) -> str:
        # The child dropdown's HTML name (= the actual filter key).
        return self.id

    @property
    def id2(self) -> str:
        return self.id

    @property
    def label2(self) -> str:
        return self.label

    lock: bool = False

    @property
    def flags(self) -> _RequiredFlag:
        return _RequiredFlag(required=False)

    # --- Cascade data feed ---
    #
    # NB: methods return raw Python data structures; the template
    # serializes them via `| tojson` to get HTML-attribute-safe JSON.
    # Returning `repr()` strings (like KYC's widget) doesn't work here
    # because the ciblage partial is loaded by `{% include %}` and goes
    # through Jinja autoescape — every `"` and `'` would be HTML-encoded
    # and the inline JS would be unparseable.

    def get_dual_tom_choices_for_js(self) -> dict:
        """Cascade options, shape per `convert_dual_choices_js`.

        Same rule as flat selectors: an option only appears if at
        least one expert in the candidate pool holds it. For the
        cascade that means:

        - **Child (`field2`)**: surviving values are those held by
          ≥1 expert *or* currently selected by the user (preserved
          across HTMX re-renders). Each child's label carries a
          `(N)` count badge — same shape as the flat selector
          labels, so the user sees the headroom before clicking.
        - **Parent (`field1`)**: keep a category only if it has at
          least one surviving child (or is currently selected as a
          parent itself). The parent's `(N)` is the sum of counts
          across its surviving children — a quick headline of how
          many experts the whole category covers.

        Note (ticket #0171) : because we drop values with 0 candidates,
        a taxonomy item visible in /admin/ontology may not appear in
        the ciblage cascade until at least one expert holds it in
        their profile. There is *no cache* to refresh — adding /
        editing an entry in /admin/ontology takes effect on the next
        request. If a journalist expects to see an item the taxonomy
        defines, the gating signal is "is any candidate-pool expert
        tagged with it?", not "is the taxonomy entry present?".
        """
        raw = convert_dual_choices_js(
            get_taxonomy_dual_select(self.taxonomy_name or "")
        )
        selected_parents = set(self._state.get(self.parent_id, []) or [])
        if isinstance(selected_parents, str):
            selected_parents = {selected_parents}

        surviving_children = []
        per_parent_count: dict[str, int] = {}
        for opt in raw["field2"]:
            value = opt["value"]
            count = self._count_by_value.get(value, 0)
            if count == 0 and value not in self.values:
                continue
            parent_key = value.split(" / ")[0]
            per_parent_count[parent_key] = per_parent_count.get(parent_key, 0) + count
            surviving_children.append(
                {"value": value, "label": f"{opt['label']} ({count})"}
            )

        surviving_parents = []
        for opt in raw["field1"]:
            parent_value = opt["value"]
            if parent_value in per_parent_count:
                surviving_parents.append(
                    {
                        "value": parent_value,
                        "label": f"{opt['label']} ({per_parent_count[parent_value]})",
                    }
                )
            elif parent_value in selected_parents:
                # Preserve user's own selection across HTMX re-renders
                # even when no expert matches any of its children.
                surviving_parents.append(
                    {"value": parent_value, "label": f"{opt['label']} (0)"}
                )
        return {"field1": surviving_parents, "field2": surviving_children}

    def get_data(self) -> list[str]:
        """Currently-selected PARENT values (init payload for the cascade)."""
        parents = self._state.get(self.parent_id, [])
        if isinstance(parents, str):
            parents = [parents]
        elif not isinstance(parents, list):
            parents = list(parents)
        return [str(p) for p in parents]

    def get_data2(self) -> list[str]:
        """Currently-selected DETAIL values."""
        return sorted(self.values)


@dataclass(frozen=True)
class _RequiredFlag:
    """Mimics `wtforms.fields.Field.flags.required` for template reuse."""

    required: bool


# ----------------------------------------------------------------
# Selector Implementations
# ----------------------------------------------------------------


class SecteurSelector(DualSelector):
    """Filter by sector of activity — two-level cascade."""

    id = "secteur"
    label = "Secteurs d'activité détaillés"
    parent_id = "secteur_parent"
    parent_label = "Catégorie de secteur"
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


class MetierSelector(DualSelector):
    id = "metier"
    label = "Métier"
    parent_id = "metier_parent"
    parent_label = "Famille de métier"
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


class FonctionPolitiquesAdministrativesSelector(DualSelector):
    id = "fonction_pol_adm"
    label = "Fonctions politiques et administratives"
    parent_id = "fonction_pol_adm_parent"
    parent_label = "Famille de fonction publique"
    taxonomy_name = "profession_fonction_public"

    def _expert_values(self, expert: User) -> Iterable[str]:
        return expert.profile.fonctions_pol_adm_detail


class FonctionOrganisationsPriveesSelector(DualSelector):
    id = "fonction_org_priv"
    label = "Fonctions organisations privées"
    parent_id = "fonction_org_priv_parent"
    parent_label = "Famille de fonction privée"
    taxonomy_name = "profession_fonction_prive"

    def _expert_values(self, expert: User) -> Iterable[str]:
        return expert.profile.fonctions_org_priv_detail


class FonctionAssociationsSyndicatsSelector(DualSelector):
    id = "fonction_ass_syn"
    label = "Fonctions associations et syndicats"
    parent_id = "fonction_ass_syn_parent"
    parent_label = "Famille de fonction associative"
    taxonomy_name = "profession_fonction_asso"

    def _expert_values(self, expert: User) -> Iterable[str]:
        return expert.profile.fonctions_ass_syn_detail


class CompetencesGeneralesSelector(DualSelector):
    id = "competences"
    label = "Compétences générales"
    parent_id = "competences_parent"
    parent_label = "Famille de compétence"
    taxonomy_name = "competence_expert"

    def _expert_values(self, expert: User) -> Iterable[str]:
        return expert.profile.competences


class CompetencesJournalismeSelector(BaseSelector):
    id = "competences_journalisme"
    label = "Compétences journalisme"
    taxonomy_name = "journalisme_competence"

    def _expert_values(self, expert: User) -> Iterable[str]:
        return expert.profile.competences_journalisme


class TypeOrganisationSelector(DualSelector):
    id = "type_organisation"
    label = "Types d'organisation"
    parent_id = "type_organisation_parent"
    parent_label = "Catégorie d'organisation"
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
