# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Unit tests for the remaining `Filter.selector` static methods in
`app.modules.swork.components.members_list` (the 4 additional
list-style filters + the 2 location filters).

Filters under test :
- `FilterBySecteurActivite` (aggregates 3 KYC sub-fields ; the
  selector picks `secteurs_activite` which is the union)
- `FilterByCompetencesGenerales`
- `FilterByCompetencesJournalisme`
- `FilterByTransformationsMajeures`
- `FilterByCountryOrm` (uses `country_code_to_country_name` to
  resolve the human label)
- `FilterByDeptOrm`
- `FilterByCityOrm`

Each selector has a « no profile » defensive branch the directory
listing page relies on so users without KYC don't crash the render.
"""

from __future__ import annotations

import pytest

from app.modules.swork.components.base import FilterOption
from app.modules.swork.components.members_list import (
    FilterByCityOrm,
    FilterByCompetencesGenerales,
    FilterByCompetencesJournalisme,
    FilterByCountryOrm,
    FilterByDeptOrm,
    FilterBySecteurActivite,
    FilterByTransformationsMajeures,
)

# ── Plain stand-in classes (no mocks) ────────────────────────────────


class _Profile:
    """Stand-in for a KYC profile — only the attrs read by selectors."""

    def __init__(self, **attrs: object) -> None:
        for k, v in attrs.items():
            setattr(self, k, v)


class _User:
    """Stand-in for `User` — selectors only read `.profile`."""

    def __init__(self, profile: _Profile | None) -> None:
        self.profile = profile


def _user(profile=None, **profile_attrs) -> _User:
    if profile is None and not profile_attrs:
        return _User(None)
    return _User(_Profile(**profile_attrs))


# ── List-style selectors with no-profile defensive branch ────────────


@pytest.mark.parametrize(
    "selector_fn",
    [
        FilterBySecteurActivite.selector,
        FilterByCompetencesGenerales.selector,
        FilterByCompetencesJournalisme.selector,
        FilterByTransformationsMajeures.selector,
    ],
)
def test_no_profile_returns_empty_list(selector_fn):
    """All 4 list-style selectors return `[]` when `user.profile`
    is None. Pin the defensive empty so the page renders for
    KYC-incomplete users."""
    result = selector_fn(_user())
    assert result == []


class TestFilterBySecteurActivite:
    def test_returns_secteurs_activite_attr(self):
        """Bug #0078 (pinned via docstring) : the filter reads
        `user.profile.secteurs_activite` — the union of the 3 KYC
        sub-fields. Pin the attr name so a rename surfaces."""
        user = _user(
            secteurs_activite=["Tech", "Média", "Santé"],
        )
        assert FilterBySecteurActivite.selector(user) == [
            "Tech",
            "Média",
            "Santé",
        ]

    def test_empty_attribute_returns_empty_list(self):
        user = _user(secteurs_activite=[])
        assert FilterBySecteurActivite.selector(user) == []


class TestFilterByCompetencesGenerales:
    def test_returns_competences_attr(self):
        """Reads `user.profile.competences` (NOT
        `competences_generales` — that's the filter id, not the
        profile attr). Pin the asymmetry so a future « consistency »
        refactor that renames the attr is caught."""
        user = _user(competences=["Communication", "Leadership"])
        assert FilterByCompetencesGenerales.selector(user) == [
            "Communication",
            "Leadership",
        ]


class TestFilterByCompetencesJournalisme:
    def test_returns_competences_journalisme_attr(self):
        user = _user(competences_journalisme=["Investigation", "Vidéo"])
        assert FilterByCompetencesJournalisme.selector(user) == [
            "Investigation",
            "Vidéo",
        ]

    def test_specifically_reads_journalisme_not_general_competences(self):
        """Cross-check that the journalisme filter doesn't
        accidentally read `competences` (the general one)."""
        user = _user(
            competences=["general only"],
            competences_journalisme=["journalism only"],
        )
        assert FilterByCompetencesJournalisme.selector(user) == ["journalism only"]


class TestFilterByTransformationsMajeures:
    def test_returns_transformations_majeures_attr(self):
        user = _user(transformations_majeures=["Digital", "Climate", "Generative AI"])
        assert FilterByTransformationsMajeures.selector(user) == [
            "Digital",
            "Climate",
            "Generative AI",
        ]


# ── Location filters (FilterByCountryOrm / DeptOrm / CityOrm) ───────


class TestFilterByCountryOrm:
    """The country selector uses `country_code_to_country_name` to
    produce a `FilterOption(human_label, country_code)`. The country
    code is the ISO-style raw value (e.g. « FR ») ; the label is
    the French name (« France »).

    NOTE : these selectors are *instance methods* (not @staticmethod)
    so we instantiate the filter first."""

    def test_returns_filteroption_with_code_and_name(self):
        f = FilterByCountryOrm()
        user = _user(country="FR")
        result = f.selector(user)
        assert isinstance(result, FilterOption)
        assert result.code == "FR"
        # The option (label) is the human form.
        assert result.option  # non-empty

    def test_unknown_country_code_still_returns_filteroption(self):
        """A country code that the lookup table doesn't know about
        still returns a FilterOption — pin so the filter dropdown
        renders SOMETHING (likely empty label, code preserved) rather
        than crashing."""
        f = FilterByCountryOrm()
        user = _user(country="ZZ")
        result = f.selector(user)
        assert isinstance(result, FilterOption)
        assert result.code == "ZZ"


class TestFilterByDeptOrm:
    def test_returns_departement_attr_as_string(self):
        """Department filter returns the bare string, NOT a
        FilterOption. Pin the asymmetric shape — code only, no
        human label (departments are already French)."""
        f = FilterByDeptOrm()
        user = _user(departement="75")
        result = f.selector(user)
        assert result == "75"
        assert isinstance(result, str)


class TestFilterByCityOrm:
    def test_returns_ville_attr_as_string(self):
        """City filter returns the city name verbatim (no label/code
        split). Pin so an accidental FilterOption wrapping doesn't
        change the dropdown shape."""
        f = FilterByCityOrm()
        user = _user(ville="Paris")
        result = f.selector(user)
        assert result == "Paris"
        assert isinstance(result, str)


# ── Cross-cutting return-shape pin ───────────────────────────────────


class TestSelectorReturnTypes:
    @pytest.mark.parametrize(
        "selector_fn",
        [
            FilterBySecteurActivite.selector,
            FilterByCompetencesGenerales.selector,
            FilterByCompetencesJournalisme.selector,
            FilterByTransformationsMajeures.selector,
        ],
    )
    def test_list_selectors_return_list(self, selector_fn):
        user = _user(
            secteurs_activite=["A"],
            competences=["A"],
            competences_journalisme=["A"],
            transformations_majeures=["A"],
        )
        result = selector_fn(user)
        assert isinstance(result, list)
