# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Unit tests for the `Filter.selector(user)` static methods in
`app.modules.swork.components.members_list`.

Six filter classes (FilterByTypeOrganisation, FilterByTypeEntrepriseMedia,
FilterByTypePresseEtMedia, FilterByTypeAgenceRP, FilterByTailleOrganisation,
FilterBySecteurActivite) follow the same pattern :

- `selector(user)` is a static method
- It reads a specific attribute of `user.profile` and returns it as
  a list / FilterOption
- When `user.profile is None`, it defensively returns an empty / null
  value rather than crashing

The « no profile » branch matters a lot : the directory listing
page must render even when some users haven't completed KYC.

This file pins the selector contracts so a future profile attr
rename doesn't silently empty out a filter.
"""

from __future__ import annotations

from typing import Any

import pytest

from app.modules.swork.components.base import FilterOption
from app.modules.swork.components.members_list import (
    FilterByCityOrm,
    FilterByCountryOrm,
    FilterByDeptOrm,
    FilterByTailleOrganisation,
    FilterByTypeAgenceRP,
    FilterByTypeEntrepriseMedia,
    FilterByTypeOrganisation,
    FilterByTypePresseEtMedia,
)


class _Profile:
    """Minimal profile stand-in : only carries the attrs the SUT
    actually reads. Unset attrs raise AttributeError on access, which
    is the right behaviour for catching « selector reads the wrong
    field » regressions."""

    def __init__(self, **attrs: Any) -> None:
        for name, value in attrs.items():
            setattr(self, name, value)


class _User:
    """Minimal user stand-in carrying an optional profile."""

    def __init__(self, profile: _Profile | None) -> None:
        self.profile = profile


def _user_with_profile(**profile_attrs: Any) -> _User:
    """Build a User stand-in with a profile carrying the given
    attrs. Pass `_profile_is_none=True` to test the « no profile »
    branch."""
    if profile_attrs.get("_profile_is_none"):
        return _User(profile=None)
    attrs = {k: v for k, v in profile_attrs.items() if k != "_profile_is_none"}
    return _User(profile=_Profile(**attrs))


# ── No-profile defensive branch ──────────────────────────────────────


@pytest.mark.parametrize(
    "selector_fn",
    [
        FilterByTypeOrganisation.selector,
        FilterByTypeEntrepriseMedia.selector,
        FilterByTypePresseEtMedia.selector,
        FilterByTypeAgenceRP.selector,
    ],
)
def test_list_selector_returns_empty_list_when_no_profile(selector_fn):
    """The 4 list-style filters all return `[]` when the user has
    no profile. Pin the defensive empty so the directory listing
    doesn't crash on unfilled KYC users."""
    user = _user_with_profile(_profile_is_none=True)
    result = selector_fn(user)
    assert result == []


def test_taille_orga_selector_returns_empty_filteroption_when_no_profile():
    """`FilterByTailleOrganisation.selector` returns a
    `FilterOption("", "")` (NOT a list) when no profile. Pin the
    asymmetric shape — single value vs. list — so a refactor
    doesn't silently homogenize them."""
    user = _user_with_profile(_profile_is_none=True)
    result = FilterByTailleOrganisation.selector(user)
    assert isinstance(result, FilterOption)
    assert result.option == ""
    assert result.code == ""


def test_country_orm_selector_returns_empty_filteroption_when_no_profile():
    """Regression : `FilterByCountryOrm.selector` used to read
    `user.profile.country` with no guard, so building the members-list
    filters over a user with no KYCProfile raised AttributeError
    ('NoneType' has no attribute 'country'). It now returns
    `FilterOption("", "")` like its siblings."""
    user = _user_with_profile(_profile_is_none=True)
    result = FilterByCountryOrm().selector(user)
    assert isinstance(result, FilterOption)
    assert result.option == ""
    assert result.code == ""


@pytest.mark.parametrize("filter_cls", [FilterByDeptOrm, FilterByCityOrm])
def test_dept_city_orm_selector_returns_empty_str_when_no_profile(filter_cls):
    """Regression companion : the dept/ville ORM filters read
    `user.profile.<attr>` directly and must return `""` (falsy, so the
    base drops it) rather than crash when the profile is missing."""
    user = _user_with_profile(_profile_is_none=True)
    assert filter_cls().selector(user) == ""


# ── FilterByTypeOrganisation ─────────────────────────────────────────


class TestFilterByTypeOrganisation:
    def test_returns_type_organisation_attr(self):
        """The selector returns the raw `type_organisation` attribute
        from the user's profile. Pin so a future ontology key rename
        is caught."""
        user = _user_with_profile(type_organisation=["Agence RP", "Média"])
        assert FilterByTypeOrganisation.selector(user) == ["Agence RP", "Média"]

    def test_empty_attribute_returns_empty_list(self):
        user = _user_with_profile(type_organisation=[])
        assert FilterByTypeOrganisation.selector(user) == []


# ── FilterByTypeEntrepriseMedia ──────────────────────────────────────


class TestFilterByTypeEntrepriseMedia:
    def test_returns_type_entreprise_media_attr(self):
        user = _user_with_profile(
            type_entreprise_media=["Quotidien", "Agence de presse"]
        )
        assert FilterByTypeEntrepriseMedia.selector(user) == [
            "Quotidien",
            "Agence de presse",
        ]

    def test_specifically_reads_the_correct_attr_not_a_neighbour(self):
        """Cross-check : the selector reads `type_entreprise_media`,
        not `type_presse_et_media`. Pin so a future copy-paste typo
        between the two filters is caught."""
        user = _user_with_profile(
            type_entreprise_media=["correct"],
            type_presse_et_media=["wrong"],
        )
        assert FilterByTypeEntrepriseMedia.selector(user) == ["correct"]


# ── FilterByTypePresseEtMedia ────────────────────────────────────────


class TestFilterByTypePresseEtMedia:
    def test_returns_type_presse_et_media_attr(self):
        user = _user_with_profile(
            type_presse_et_media=["Quotidien national", "Hebdomadaire régional"]
        )
        assert FilterByTypePresseEtMedia.selector(user) == [
            "Quotidien national",
            "Hebdomadaire régional",
        ]


# ── FilterByTypeAgenceRP ─────────────────────────────────────────────


class TestFilterByTypeAgenceRP:
    def test_returns_type_agence_rp_attr(self):
        user = _user_with_profile(type_agence_rp=["RP Corporate", "RP Politique"])
        assert FilterByTypeAgenceRP.selector(user) == [
            "RP Corporate",
            "RP Politique",
        ]


# ── FilterByTailleOrganisation ───────────────────────────────────────


class TestFilterByTailleOrganisation:
    """Asymmetric : returns a single `FilterOption(label, code)` —
    not a list. The `taille_orga` ontology is a single-select field
    (one bucket per user) versus the multi-select pattern of the
    other filters above."""

    def test_returns_filteroption_with_label_and_code(self):
        user = _user_with_profile(info_professionnelle={"taille_orga": "10"})
        result = FilterByTailleOrganisation.selector(user)
        assert isinstance(result, FilterOption)
        # Code is the raw ontology value ; option is the human form.
        assert result.code == "10"
        assert "10" in result.option  # via _taille_orga_label

    def test_uses_taille_orga_label_for_display(self):
        """Cross-check that the selector routes through
        `_taille_orga_label` — the « 1 personne » special case is
        the cleanest signal."""
        user = _user_with_profile(info_professionnelle={"taille_orga": "1"})
        result = FilterByTailleOrganisation.selector(user)
        assert result.option == "1 personne"
        assert result.code == "1"

    def test_missing_taille_orga_key_returns_empty_option(self):
        """The `info_professionnelle` dict may not yet have a
        `taille_orga` key (partial KYC) — pin the empty fallback."""
        user = _user_with_profile(info_professionnelle={})
        result = FilterByTailleOrganisation.selector(user)
        assert isinstance(result, FilterOption)
        assert result.option == ""
        assert result.code == ""

    def test_empty_string_value_returns_empty_option(self):
        """A `taille_orga: ""` value is honest-to-goodness empty.
        Pin the truthy check so a future « return option even for
        empty string » regression that pollutes the filter dropdown
        with blank entries is caught."""
        user = _user_with_profile(info_professionnelle={"taille_orga": ""})
        result = FilterByTailleOrganisation.selector(user)
        assert isinstance(result, FilterOption)
        assert result.code == ""
        assert result.option == ""

    def test_value_coerced_to_str_before_label_lookup(self):
        """An accidental integer value (KYC migration bug) is
        coerced to str before being looked up. Pin so a future
        regression that crashes with TypeError on integer values
        is caught."""
        user = _user_with_profile(info_professionnelle={"taille_orga": 1})
        result = FilterByTailleOrganisation.selector(user)
        # Should produce the « 1 personne » singular label.
        assert result.option == "1 personne"
        assert result.code == "1"


class TestFilterSelectorReturnTypes:
    """Pin the return types so a refactor that changes the contract
    surfaces immediately."""

    @pytest.mark.parametrize(
        "selector_fn",
        [
            FilterByTypeOrganisation.selector,
            FilterByTypeEntrepriseMedia.selector,
            FilterByTypePresseEtMedia.selector,
            FilterByTypeAgenceRP.selector,
        ],
    )
    def test_list_selectors_return_list(self, selector_fn):
        """The 4 list-shaped filters return `list[str]`."""
        user = _user_with_profile(
            type_organisation=["A"],
            type_entreprise_media=["A"],
            type_presse_et_media=["A"],
            type_agence_rp=["A"],
        )
        result = selector_fn(user)
        assert isinstance(result, list)
