# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Unit tests for the Organisations-side filter classes in
`app.modules.swork.components.organisations_list`.

The org filters use a DIFFERENT pattern from the members_list filters
(which are covered by `test_filter_selectors.py` and
`test_more_filter_selectors.py`) :

- There is NO `selector(user)` static method.
- The 4 JSON-array filters share `_OrgListJsonArrayFilter`, which
  reads from `BusinessWall` objects passed to `__init__(bws)` and
  pulls a class-level `bw_field` attribute to know WHICH JSON list
  column to read.
- `FilterByCategory` is shape-different : its options are a fixed
  class-level list (no DB-derived options) mapped to BWType values.
- `FilterByCountryOrm` / `FilterByDeptOrm` / `FilterByCityOrm` take
  pre-fetched code/name lists and don't need BW objects at all.

We pin :
  1. The defensive « no bws / empty bws » branch — the listing page
     must render even when the active BusinessWall set is empty.
  2. Each filter reads its OWN `bw_field` (cross-check : a TypeAgenceRP
     copy-paste typo would surface immediately).
  3. The shared `_OrgListJsonArrayFilter` logic : non-list raw values
     are tolerated, falsy entries are dropped, values are coerced to
     `str`, and the result is sorted+deduped.
  4. Return-type contracts for the 3 location filters (str vs.
     FilterOption — they are NOT homogeneous, which is intentional).
  5. The `FilterByCategory.bw_type_map` translation table — pinned so
     a future bw_type ontology rename surfaces.

This file complements (does not duplicate) the existing tests for
`FilterByTailleOrganisation`, `_taille_orga_label`, etc., which live
in `test_taille_orga_label.py`.
"""

from __future__ import annotations

import pytest

from app.modules.swork.components.base import Filter, FilterOption
from app.modules.swork.components.organisations_list import (
    FilterByCategory,
    FilterByCityOrm,
    FilterByCountryOrm,
    FilterByDeptOrm,
    OrgFilterBySecteurActivite,
    OrgFilterByTypeAgenceRP,
    OrgFilterByTypeOrganisation,
    OrgFilterByTypePresseEtMedia,
    _OrgListJsonArrayFilter,
)


class _FakeBW:
    """Duck-typed stand-in for `BusinessWall`. The JSON-array filters
    only call `getattr(bw, self.bw_field, None)`, so we only need to
    set whatever attribute the filter under test will read."""

    def __init__(self, **attrs: object) -> None:
        for key, value in attrs.items():
            setattr(self, key, value)


_JSON_ARRAY_FILTERS: list[tuple[type[_OrgListJsonArrayFilter], str]] = [
    (OrgFilterByTypeOrganisation, "type_organisation"),
    (OrgFilterByTypePresseEtMedia, "type_presse_et_media"),
    (OrgFilterByTypeAgenceRP, "type_agence_rp"),
    (OrgFilterBySecteurActivite, "secteurs_activite_detail"),
]


# ── Class-level identity (id / label / bw_field) ─────────────────────


class TestJsonArrayFilterClassContract:
    """Pin the class-level identity of each JSON-array filter. A
    rename of `id` would break URL state ; a rename of `bw_field`
    would silently empty out the filter dropdown."""

    @pytest.mark.parametrize(
        ("cls", "expected_id", "expected_field"),
        [
            (OrgFilterByTypeOrganisation, "type_organisation", "type_organisation"),
            (
                OrgFilterByTypePresseEtMedia,
                "type_presse_et_media",
                "type_presse_et_media",
            ),
            (OrgFilterByTypeAgenceRP, "type_agence_rp", "type_agence_rp"),
            (
                OrgFilterBySecteurActivite,
                "secteur_activite",
                "secteurs_activite_detail",
            ),
        ],
    )
    def test_id_and_bw_field_pinned(
        self, cls: type[_OrgListJsonArrayFilter], expected_id: str, expected_field: str
    ) -> None:
        """The `id` (URL state key) and `bw_field` (DB column) can
        legitimately diverge — `OrgFilterBySecteurActivite` does so
        — so we pin both independently."""
        assert cls.id == expected_id
        assert cls.bw_field == expected_field

    @pytest.mark.parametrize(("cls", "_field"), _JSON_ARRAY_FILTERS)
    def test_label_is_non_empty(
        self, cls: type[_OrgListJsonArrayFilter], _field: str
    ) -> None:
        assert isinstance(cls.label, str)
        assert cls.label.strip()

    @pytest.mark.parametrize(("cls", "_field"), _JSON_ARRAY_FILTERS)
    def test_inherits_from_shared_base(
        self, cls: type[_OrgListJsonArrayFilter], _field: str
    ) -> None:
        """All 4 JSON-list filters share `_OrgListJsonArrayFilter`.
        Pin the inheritance so a future « inline the base » refactor
        that loses the uniform shape is caught."""
        assert issubclass(cls, _OrgListJsonArrayFilter)
        assert issubclass(cls, Filter)


# ── Defensive « no bws / empty bws » branch ──────────────────────────


class TestJsonArrayFilterDefensiveBranch:
    """The organisations directory must render even when no active
    BusinessWall exists (fresh install / all-suspended state)."""

    @pytest.mark.parametrize(("cls", "_field"), _JSON_ARRAY_FILTERS)
    def test_no_bws_yields_empty_options(
        self, cls: type[_OrgListJsonArrayFilter], _field: str
    ) -> None:
        """Constructing with no `bws` argument falls through to the
        class-level empty `options` list."""
        assert cls().options == []

    @pytest.mark.parametrize(("cls", "_field"), _JSON_ARRAY_FILTERS)
    def test_empty_bws_list_yields_empty_options(
        self, cls: type[_OrgListJsonArrayFilter], _field: str
    ) -> None:
        """An empty list (truthiness-equivalent to None) also returns
        early before the value-collection loop."""
        assert cls([]).options == []

    @pytest.mark.parametrize(("cls", "_field"), _JSON_ARRAY_FILTERS)
    def test_none_bws_yields_empty_options(
        self, cls: type[_OrgListJsonArrayFilter], _field: str
    ) -> None:
        assert cls(None).options == []


# ── Per-filter reads-its-own-attr (cross-check) ──────────────────────


class TestJsonArrayFilterReadsItsOwnField:
    """Cross-check : each filter reads ONLY its own `bw_field` and
    ignores the others. A copy-paste typo (e.g. TypeAgenceRP
    accidentally reading `type_organisation`) would surface here."""

    @pytest.mark.parametrize(("cls", "field"), _JSON_ARRAY_FILTERS)
    def test_picks_up_own_field_values(
        self, cls: type[_OrgListJsonArrayFilter], field: str
    ) -> None:
        bw = _FakeBW(**{field: ["alpha", "beta"]})
        assert cls([bw]).options == ["alpha", "beta"]

    @pytest.mark.parametrize(("cls", "field"), _JSON_ARRAY_FILTERS)
    def test_ignores_other_fields(
        self, cls: type[_OrgListJsonArrayFilter], field: str
    ) -> None:
        """Set ALL the fields to distinct values ; the filter must
        only pick up its own."""
        all_fields = {f: [f"noise-from-{f}"] for _c, f in _JSON_ARRAY_FILTERS}
        all_fields[field] = ["correct"]
        bw = _FakeBW(**all_fields)
        assert cls([bw]).options == ["correct"]


# ── Shared `_OrgListJsonArrayFilter.__init__` value-collection logic ─


class TestSharedValueCollection:
    """The shared base does the heavy lifting : merge across bws,
    dedupe via set, filter falsy entries, coerce to str, sort."""

    def test_values_are_merged_across_bws_and_deduped(self) -> None:
        bws = [
            _FakeBW(type_organisation=["A", "B"]),
            _FakeBW(type_organisation=["B", "C"]),
            _FakeBW(type_organisation=["A"]),
        ]
        assert OrgFilterByTypeOrganisation(bws).options == ["A", "B", "C"]

    def test_values_are_sorted_lexicographically(self) -> None:
        """The base uses `sorted()` so options always appear in a
        stable order in the dropdown — pin this so a future « keep
        insertion order » refactor is caught."""
        bws = [_FakeBW(type_organisation=["zebra", "alpha", "mango"])]
        assert OrgFilterByTypeOrganisation(bws).options == [
            "alpha",
            "mango",
            "zebra",
        ]

    def test_non_list_raw_value_is_tolerated(self) -> None:
        """`getattr(bw, field, None) or []` plus the `isinstance(raw,
        list)` check means a string column value is silently dropped
        instead of crashing. Pin so a future strict-type refactor
        doesn't break the listing for one bad BW."""
        bws = [
            _FakeBW(type_organisation="not a list"),
            _FakeBW(type_organisation=["valid"]),
        ]
        assert OrgFilterByTypeOrganisation(bws).options == ["valid"]

    def test_none_raw_value_is_tolerated(self) -> None:
        bws = [
            _FakeBW(type_organisation=None),
            _FakeBW(type_organisation=["valid"]),
        ]
        assert OrgFilterByTypeOrganisation(bws).options == ["valid"]

    def test_missing_attr_is_tolerated(self) -> None:
        """`getattr(..., None)` means a BW without the column at all
        (legacy row) doesn't crash."""
        bw_without_field = _FakeBW()  # no attrs at all
        bw_with_field = _FakeBW(type_organisation=["valid"])
        assert OrgFilterByTypeOrganisation(
            [bw_without_field, bw_with_field]
        ).options == ["valid"]

    def test_falsy_entries_are_filtered_out(self) -> None:
        """`str(v) for v in raw if v` drops None, "", 0 entries — pin
        so blank entries don't pollute the dropdown."""
        bws = [_FakeBW(type_organisation=["A", None, "", "B", 0])]
        assert OrgFilterByTypeOrganisation(bws).options == ["A", "B"]

    def test_non_string_values_are_coerced_to_str(self) -> None:
        """Integer values (KYC migration quirk) are coerced via
        `str(v)`. Pin so the resulting options stay sortable and
        usable as dict keys."""
        bws = [_FakeBW(type_organisation=[1, 2, "A"])]
        # sorted lexicographically over the coerced strings.
        assert OrgFilterByTypeOrganisation(bws).options == ["1", "2", "A"]


# ── FilterByCategory : a different shape (fixed class-level options) ─


class TestFilterByCategory:
    """`FilterByCategory` is the odd one out : it has a FIXED
    class-level options list and a `bw_type_map` translation table
    from human label → BWType value. No DB derivation."""

    def test_options_are_class_level_and_pinned(self) -> None:
        """Pin the user-facing labels — a translation rename would
        break URL state for in-flight links from emails / bookmarks."""
        assert FilterByCategory.options == [
            "Agences de presse",
            "Médias",
            "PR agencies",
            "Autres",
        ]

    def test_id_and_label_pinned(self) -> None:
        assert FilterByCategory.id == "category"
        assert FilterByCategory.label == "Categorie"

    def test_bw_type_map_translation(self) -> None:
        """Pin the translation table so a future BWType ontology
        rename surfaces. The `None` values are intentional :
        « Autres » and « Non officialisées » are handled separately
        in the `.apply()` path (excluded / OR-clause)."""
        assert FilterByCategory.bw_type_map == {
            "Agences de presse": "media",
            "Médias": "media",
            "PR agencies": "pr",
            "Autres": None,
            "Non officialisées": None,
        }

    def test_press_agencies_and_media_both_map_to_media(self) -> None:
        """Two distinct user-facing labels share the `media` BWType
        bucket — pin so a future « split press agencies into their
        own BWType » refactor is intentional, not accidental."""
        m = FilterByCategory.bw_type_map
        assert m["Agences de presse"] == m["Médias"] == "media"


# ── Location filters : FilterByCountryOrm / DeptOrm / CityOrm ────────


class TestFilterByCountryOrm:
    """`FilterByCountryOrm` wraps each code in a
    `FilterOption(human_name, code)`. The human name comes from the
    KYC `pays` ontology — we can't test it in pure unit mode (DB
    lookup) — so we focus on the defensive branches and the
    `get_country_codes` state-projection helper."""

    def test_no_codes_yields_empty_options(self) -> None:
        assert FilterByCountryOrm().options == []

    def test_empty_codes_list_yields_empty_options(self) -> None:
        """An empty list (falsy) skips the FilterOption build loop."""
        assert FilterByCountryOrm(codes=[]).options == []

    def test_none_codes_yields_empty_options(self) -> None:
        assert FilterByCountryOrm(codes=None).options == []

    def test_id_and_label_pinned(self) -> None:
        assert FilterByCountryOrm.id == "country"
        assert FilterByCountryOrm.label == "Pays"

    def test_get_country_codes_projects_active_options(self) -> None:
        """`get_country_codes(state)` reads `FilterOption.code` —
        NOT the index, NOT the label — for each truthy state entry.
        Pin so a refactor that changes the state key shape
        ({str: bool} → {int: bool}) surfaces."""
        f = FilterByCountryOrm()
        f.options = [
            FilterOption("France", "FR"),
            FilterOption("Belgique", "BE"),
            FilterOption("Allemagne", "DE"),
        ]
        state = {"0": True, "1": False, "2": True}
        assert f.get_country_codes(state) == ["FR", "DE"]

    def test_get_country_codes_returns_empty_when_no_state_active(self) -> None:
        f = FilterByCountryOrm()
        f.options = [FilterOption("France", "FR")]
        assert f.get_country_codes({"0": False}) == []


class TestFilterByDeptOrm:
    """`FilterByDeptOrm` stores raw strings (no FilterOption wrap) —
    departments are already French codes and don't need a label
    lookup."""

    def test_id_and_label_pinned(self) -> None:
        assert FilterByDeptOrm.id == "dept"
        assert FilterByDeptOrm.label == "Département"

    def test_no_names_yields_empty_options(self) -> None:
        assert FilterByDeptOrm().options == []

    def test_none_names_yields_empty_options(self) -> None:
        assert FilterByDeptOrm(names=None).options == []

    def test_empty_names_list_yields_empty_options(self) -> None:
        assert FilterByDeptOrm(names=[]).options == []

    def test_names_are_stored_as_raw_strings(self) -> None:
        """Pin the asymmetric shape — `list[str]`, NOT
        `list[FilterOption]`. A future « consistency » refactor that
        wraps in FilterOption would break the active_filters
        rendering."""
        f = FilterByDeptOrm(names=["75", "92", "13"])
        assert f.options == ["75", "92", "13"]
        for opt in f.options:
            assert isinstance(opt, str)


class TestFilterByCityOrm:
    """`FilterByCityOrm` shares `FilterByDeptOrm`'s shape : raw
    strings, no FilterOption wrap."""

    def test_id_and_label_pinned(self) -> None:
        assert FilterByCityOrm.id == "city"
        assert FilterByCityOrm.label == "Ville"

    def test_no_names_yields_empty_options(self) -> None:
        assert FilterByCityOrm().options == []

    def test_none_names_yields_empty_options(self) -> None:
        assert FilterByCityOrm(names=None).options == []

    def test_empty_names_list_yields_empty_options(self) -> None:
        assert FilterByCityOrm(names=[]).options == []

    def test_names_are_stored_as_raw_strings(self) -> None:
        f = FilterByCityOrm(names=["Paris", "Lyon"])
        assert f.options == ["Paris", "Lyon"]
        for opt in f.options:
            assert isinstance(opt, str)


# ── Cross-cutting return-shape pin ───────────────────────────────────


class TestReturnTypes:
    """Pin the return-shape contract for the 4 JSON-array filters and
    the location filters. A refactor that changes any of these
    homogeneously (e.g. wrapping everything in FilterOption) would
    surface here."""

    @pytest.mark.parametrize(("cls", "field"), _JSON_ARRAY_FILTERS)
    def test_json_array_options_are_list_of_str(
        self, cls: type[_OrgListJsonArrayFilter], field: str
    ) -> None:
        bw = _FakeBW(**{field: ["A", "B"]})
        result = cls([bw]).options
        assert isinstance(result, list)
        for opt in result:
            assert isinstance(opt, str)

    def test_dept_options_are_list_of_str(self) -> None:
        assert all(isinstance(o, str) for o in FilterByDeptOrm(names=["75"]).options)

    def test_city_options_are_list_of_str(self) -> None:
        assert all(isinstance(o, str) for o in FilterByCityOrm(names=["Paris"]).options)
