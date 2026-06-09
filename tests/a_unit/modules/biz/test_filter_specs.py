# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Unit tests for the FILTER_SPECS / JOURNALISM_FILTER_SPECS / TABS
constants in `app.modules.biz.views._common`.

These constants drive the MARKET filter sidebar and the top-level tab
strip. They're consumed by `_get_filters()` and `_get_tabs()` in
`home.py`, both of which iterate dictionaries that must satisfy
specific invariants (every entry has an `id`, the `id` is unique
across the list, ontology keys exist).

A silent removal here (« I'll just drop one filter from the list »)
visibly breaks the UI but only on the affected category — it would
not crash any test unless the invariant is pinned.
"""

from __future__ import annotations

from app.modules.biz.views._common import (
    FILTER_SPECS,
    JOURNALISM_FILTER_SPECS,
    TABS,
)


class TestTabs:
    def test_tabs_list_is_non_empty(self):
        assert len(TABS) > 0

    def test_every_tab_has_id_and_label(self):
        for tab in TABS:
            assert "id" in tab, f"Tab missing 'id': {tab!r}"
            assert "label" in tab, f"Tab missing 'label': {tab!r}"
            assert isinstance(tab["id"], str)
            assert tab["id"]
            assert isinstance(tab["label"], str)
            assert tab["label"]

    def test_tab_ids_are_unique(self):
        """Two tabs with the same id would race on URL routing : the
        `current_tab` query param would match both, and `_get_tabs`
        would mark both as « current ». Pin uniqueness here so a
        copy-paste mistake is caught immediately."""
        ids = [t["id"] for t in TABS]
        assert len(ids) == len(set(ids)), f"Duplicate tab ids: {ids}"

    def test_canonical_tabs_present(self):
        """The 5 canonical MARKET tabs are part of the public API
        (URL params, nav labels). Pin so a future refactor doesn't
        silently drop one and route 5xx on /biz/?current_tab=missions."""
        ids = {t["id"] for t in TABS}
        for canonical in ("stories", "subscriptions", "missions", "projects", "jobs"):
            assert canonical in ids, f"canonical tab {canonical!r} missing from TABS"


class TestFilterSpecs:
    def test_filter_specs_list_is_non_empty(self):
        assert len(FILTER_SPECS) > 0

    def test_every_filter_has_id_and_label(self):
        for spec in FILTER_SPECS:
            assert "id" in spec, f"FilterSpec missing 'id': {spec!r}"
            assert "label" in spec, f"FilterSpec missing 'label': {spec!r}"

    def test_filter_ids_are_unique(self):
        ids = [s["id"] for s in FILTER_SPECS]
        assert len(ids) == len(set(ids)), f"Duplicate filter ids: {ids}"

    def test_canonical_filters_present(self):
        """Generic filters that appear on every MARKET tab."""
        ids = {s["id"] for s in FILTER_SPECS}
        for canonical in ("sector", "topic", "genre", "location", "language"):
            assert canonical in ids, (
                f"canonical filter {canonical!r} missing from FILTER_SPECS"
            )

    def test_options_or_selector_drives_each_filter(self):
        """`_get_filters()` reads either `options` (hardcoded list) or
        `selector` (column name → distinct-values DB query). A filter
        with neither would render an empty dropdown and fail silently."""
        for spec in FILTER_SPECS:
            has_options = bool(spec.get("options"))
            has_selector = bool(spec.get("selector"))
            assert has_options or has_selector, (
                f"FilterSpec {spec['id']!r} has neither `options` "
                "nor `selector` — would render an empty dropdown."
            )


class TestJournalismFilterSpecs:
    """The expanded filter sidebar for MARKET/Missions when the user
    has picked the Journalism category (ticket #0202). Each entry is
    backed by a KYC ontology slug, except for `work_mode` /
    `budget_min` / `budget_max` / `deadline` / `pays` /
    `code_postal_ville` which are free-input filters."""

    def test_specs_list_is_non_empty(self):
        assert len(JOURNALISM_FILTER_SPECS) > 0

    def test_every_spec_has_id_and_label(self):
        for spec in JOURNALISM_FILTER_SPECS:
            assert "id" in spec
            assert "label" in spec
            assert isinstance(spec["id"], str)
            assert spec["id"]
            assert isinstance(spec["label"], str)
            assert spec["label"]

    def test_ids_are_unique(self):
        ids = [s["id"] for s in JOURNALISM_FILTER_SPECS]
        assert len(ids) == len(set(ids)), (
            f"Duplicate JOURNALISM_FILTER_SPECS ids: {ids}"
        )

    def test_ids_are_disjoint_from_generic_filters(self):
        """The journalism filters are APPENDED to FILTER_SPECS in
        `_get_filters()`. If any id overlapped, the dropdown would
        render twice. Pin disjointness."""
        generic = {s["id"] for s in FILTER_SPECS}
        journalism = {s["id"] for s in JOURNALISM_FILTER_SPECS}
        assert not (generic & journalism), (
            f"FILTER_SPECS and JOURNALISM_FILTER_SPECS share ids: "
            f"{generic & journalism}"
        )

    def test_ontology_backed_filters_carry_ontology_key(self):
        """Specs with `ontology_key` get their options from the KYC
        ontology registry. Specs with `options` use a hardcoded list
        (work_mode). Specs with neither — like budget / dates / pays —
        are rendered as free input. Pin that every spec has at least
        one of the three so `_get_filters()` always knows what to do."""
        for spec in JOURNALISM_FILTER_SPECS:
            has_ontology = bool(spec.get("ontology_key"))
            has_options = bool(spec.get("options"))
            # Free-input filters are recognised by having neither, an
            # empty options list, and a non-ontology id.
            is_free_input_id = spec["id"] in {
                "budget_min",
                "budget_max",
                "deadline",
                "pays",
                "code_postal_ville",
            }
            assert has_ontology or has_options or is_free_input_id, (
                f"JOURNALISM_FILTER_SPEC {spec['id']!r} has no way to render"
            )

    def test_erick_canonical_filters_present(self):
        """The 13 filters Erick spec'd in #0202. Pin the list so a
        future refactor doesn't silently drop one."""
        ids = {s["id"] for s in JOURNALISM_FILTER_SPECS}
        for canonical in (
            "metiers_journalisme",
            "types_entreprises_presse_medias",
            "types_presse_medias",
            "competences_journalisme",
            "langues",
            "types_contenus_editoriaux",
            "modes_remuneration",
            "work_mode",
            "budget_min",
            "budget_max",
            "deadline",
            "pays",
            "code_postal_ville",
        ):
            assert canonical in ids, (
                f"Erick filter {canonical!r} missing from "
                "JOURNALISM_FILTER_SPECS — see ticket #0202."
            )
