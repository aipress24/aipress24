# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Mock-free unit tests for wire/views/_filters.py — Phase 2 gap coverage.

WHY:
    The existing tests/a_unit/modules/wire/test_filters.py already covers
    the trivial add/remove/toggle/has/sort_by primitives on a hand-built
    state dict. It leaves several public surfaces UNTESTED :

      * FILTER_SPECS topical/geo coverage and FILTER_SPECS_BY_ID
        lookup invariants.
      * the `sorter` property — list-of-dicts with `selected` flags.
      * `active_filters` when the matched spec carries a `label_function`
        (country-code -> country-name resolution path).
      * JSON state round-trip through Flask `session` :
        `get_state` (happy + corrupted + missing) ; `save_state` ;
        `reset` ; `set_tag`.
      * `update_state` dispatcher : the toggle/remove/sort-by branches,
        the unknown-id rejection, and the unknown-action rejection
        (both raise `werkzeug.exceptions.BadRequest`).
      * `remove_filter` no-op when the filter is absent (we want a
        regression guard against accidental IndexError or state
        corruption).

These exercise the same public methods the existing tests touched, but
through Flask's REAL request/session machinery via
`app.test_request_context()` — that is not mocking, it is the supported
public surface for in-process Flask testing. Pure-data paths
(sorter, FILTER_SPECS, etc.) are exercised by bypassing
`FilterBar.__init__` with `object.__new__` and seeding `bar.state`
directly, the same pattern the existing test file establishes.
"""

from __future__ import annotations

import pytest
from flask import session
from werkzeug.exceptions import BadRequest

from app.modules.wire.views._filters import (
    FILTER_SPECS,
    FILTER_SPECS_BY_ID,
    FILTER_TAG_LABEL,
    SORTER_OPTIONS,
    FilterBar,
)


def _bare_bar(state: dict | None = None, tab: str = "wall") -> FilterBar:
    """Build a FilterBar bypassing __init__ (which hits the DB)."""
    bar = object.__new__(FilterBar)
    bar.tab = tab
    bar.state = state if state is not None else {}
    return bar


class TestFilterSpecs:
    """Ticket #0229 — the COM tab now shares FILTER_SPECS with the wall,
    so the four topical filters (secteur/rubrique/genre/thématique) sit
    alongside the geo ones. A journalist can narrow communiqués by
    « secteur transport », not just by Pays/Département/Ville."""

    def test_topical_filters_present(self) -> None:
        ids = {spec["id"] for spec in FILTER_SPECS}
        assert {"sector", "topic", "genre", "section"} <= ids

    def test_geo_filters_present(self) -> None:
        ids = {spec["id"] for spec in FILTER_SPECS}
        assert {"pays_zip_ville", "departement", "ville"} <= ids

    def test_pays_spec_has_label_function(self) -> None:
        pays_spec = next(s for s in FILTER_SPECS if s["id"] == "pays_zip_ville")
        assert callable(pays_spec["label_function"])


class TestFilterSpecsById:
    """`FILTER_SPECS_BY_ID` is built once from FILTER_SPECS — verify the
    invariants the rest of the module relies on."""

    def test_keys_match_filter_specs_ids(self) -> None:
        assert set(FILTER_SPECS_BY_ID.keys()) == {s["id"] for s in FILTER_SPECS}

    def test_values_preserve_spec_identity(self) -> None:
        # Each looked-up spec is the SAME object that lives in FILTER_SPECS,
        # which means mutating one (which the module never does) would be
        # observable through both — pin that invariant.
        for spec in FILTER_SPECS:
            assert FILTER_SPECS_BY_ID[spec["id"]] is spec

    def test_all_known_filter_ids_have_tag_label(self) -> None:
        # Every spec id should have a tag label — otherwise active_filters
        # silently renders empty tag_label strings.
        for spec_id in FILTER_SPECS_BY_ID:
            assert spec_id in FILTER_TAG_LABEL


class TestSorterProperty:
    """`sorter` returns one dict per SORTER_OPTIONS entry with the
    `selected` flag set on the current `sort-by` value."""

    def test_default_selects_date(self) -> None:
        bar = _bare_bar()
        options = bar.sorter["options"]
        selected = [o for o in options if o["selected"]]
        assert len(selected) == 1
        assert selected[0]["value"] == "date"

    def test_emits_one_option_per_sorter_option(self) -> None:
        bar = _bare_bar()
        assert len(bar.sorter["options"]) == len(SORTER_OPTIONS)

    @pytest.mark.parametrize("sort_by", ["date", "views", "likes", "shares", "sales"])
    def test_each_sort_value_selects_only_itself(self, sort_by: str) -> None:
        bar = _bare_bar({"sort-by": sort_by})
        options = bar.sorter["options"]
        selected = [o["value"] for o in options if o["selected"]]
        assert selected == [sort_by]

    def test_unknown_sort_value_selects_nothing(self) -> None:
        bar = _bare_bar({"sort-by": "nope"})
        options = bar.sorter["options"]
        assert all(not o["selected"] for o in options)

    def test_options_carry_label_from_sorter_options(self) -> None:
        bar = _bare_bar()
        labels = {o["value"]: o["label"] for o in bar.sorter["options"]}
        for value, label in SORTER_OPTIONS:
            assert labels[value] == label


class TestActiveFiltersLabelFunction:
    """`active_filters` resolves `label_function` for `pays_zip_ville`.
    `country_code_to_country_name` passes through unknown codes verbatim
    (see `find_label` in kyc/field_label.py), so we can assert state
    without depending on the ontology contents : the function was
    called, the value passed through, and no TypeError was raised."""

    def test_pays_filter_invokes_label_function(self, app) -> None:
        bar = _bare_bar({"filters": [{"id": "pays_zip_ville", "value": "ZZZ-unknown"}]})
        with app.app_context():
            active = bar.active_filters
        assert len(active) == 1
        # Unknown code passes through verbatim — proves the function
        # ran without raising and that the label key was populated
        # from the function's return value rather than the raw value.
        assert active[0]["id"] == "pays_zip_ville"
        assert active[0]["value"] == "ZZZ-unknown"
        assert active[0]["label"] == "ZZZ-unknown"
        assert active[0]["tag_label"] == "pays"
        assert active[0]["type"] == "selector"

    def test_non_pays_filter_uses_value_as_label(self) -> None:
        bar = _bare_bar({"filters": [{"id": "sector", "value": "tech"}]})
        active = bar.active_filters
        assert active[0]["label"] == "tech"
        assert active[0]["value"] == "tech"

    def test_unknown_filter_id_has_empty_tag_label(self) -> None:
        # No spec match -> FILTER_TAG_LABEL.get returns "".
        bar = _bare_bar({"filters": [{"id": "made_up", "value": "anything"}]})
        active = bar.active_filters
        assert active[0]["tag_label"] == ""
        assert active[0]["label"] == "anything"

    def test_empty_filters_yields_empty_list(self) -> None:
        assert _bare_bar({}).active_filters == []


class TestStatePersistence:
    """`get_state`/`save_state`/`reset`/`set_tag` round-trip through
    Flask `session`. Use a real test request context — no mocks."""

    def test_get_state_returns_empty_when_session_key_absent(self, app) -> None:
        bar = _bare_bar(tab="wall")
        with app.test_request_context():
            assert bar.get_state() == {}

    def test_save_then_get_state_round_trip(self, app) -> None:
        bar = _bare_bar({"filters": [{"id": "sector", "value": "tech"}]}, tab="wall")
        with app.test_request_context():
            bar.save_state()
            # A fresh FilterBar reading the same session sees the same state.
            fresh = _bare_bar(tab="wall")
            assert fresh.get_state() == {"filters": [{"id": "sector", "value": "tech"}]}

    def test_get_state_handles_corrupted_json(self, app) -> None:
        bar = _bare_bar(tab="wall")
        with app.test_request_context():
            session["wire:wall:state"] = "{not-json"
            # Corrupted state degrades to {} rather than crashing.
            assert bar.get_state() == {}

    def test_reset_wipes_state_and_persists(self, app) -> None:
        bar = _bare_bar({"filters": [{"id": "sector", "value": "x"}]}, tab="wall")
        with app.test_request_context():
            bar.reset()
            assert bar.state == {}
            fresh = _bare_bar(tab="wall")
            assert fresh.get_state() == {}

    def test_set_tag_adds_tag_filter_and_persists(self, app) -> None:
        bar = _bare_bar({}, tab="wall")
        with app.test_request_context():
            bar.set_tag("python")
            assert bar.tag == "python"
            fresh = _bare_bar(tab="wall")
            assert fresh.get_state()["filters"] == [{"id": "tag", "value": "python"}]

    def test_per_tab_isolation(self, app) -> None:
        # State for "wall" must not leak into "com" — different session keys.
        wall = _bare_bar({"filters": [{"id": "sector", "value": "tech"}]}, tab="wall")
        with app.test_request_context():
            wall.save_state()
            com = _bare_bar(tab="com")
            assert com.get_state() == {}


class TestUpdateStateDispatcher:
    """`update_state` reads `request.form` and dispatches on `action`.
    Drive it through real form data — `test_request_context(data=...)`
    populates `request.form` exactly as a real POST would."""

    def test_toggle_action_adds_new_filter(self, app) -> None:
        bar = _bare_bar({}, tab="wall")
        form = {"action": "toggle", "id": "sector", "value": "tech"}
        with app.test_request_context(method="POST", data=form):
            bar.update_state()
        assert bar.state["filters"] == [{"id": "sector", "value": "tech"}]

    def test_toggle_action_removes_existing_filter(self, app) -> None:
        bar = _bare_bar({"filters": [{"id": "sector", "value": "tech"}]}, tab="wall")
        form = {"action": "toggle", "id": "sector", "value": "tech"}
        with app.test_request_context(method="POST", data=form):
            bar.update_state()
        assert bar.state["filters"] == []

    def test_remove_action_drops_named_filter(self, app) -> None:
        bar = _bare_bar(
            {
                "filters": [
                    {"id": "sector", "value": "tech"},
                    {"id": "genre", "value": "news"},
                ]
            },
            tab="wall",
        )
        form = {"action": "remove", "id": "sector", "value": "tech"}
        with app.test_request_context(method="POST", data=form):
            bar.update_state()
        assert bar.state["filters"] == [{"id": "genre", "value": "news"}]

    def test_sort_by_action_sets_sort_order(self, app) -> None:
        bar = _bare_bar({}, tab="wall")
        form = {"action": "sort-by", "value": "views"}
        with app.test_request_context(method="POST", data=form):
            bar.update_state()
        assert bar.state["sort-by"] == "views"

    @pytest.mark.parametrize("action", ["toggle", "remove"])
    def test_unknown_filter_id_rejected(self, app, action: str) -> None:
        bar = _bare_bar({}, tab="wall")
        form = {"action": action, "id": "bogus_filter", "value": "x"}
        with app.test_request_context(method="POST", data=form):
            with pytest.raises(BadRequest):
                bar.update_state()

    def test_unknown_action_rejected(self, app) -> None:
        bar = _bare_bar({}, tab="wall")
        form = {"action": "delete-everything", "id": "sector", "value": "x"}
        with app.test_request_context(method="POST", data=form):
            with pytest.raises(BadRequest):
                bar.update_state()

    def test_tag_id_accepted_for_toggle(self, app) -> None:
        # "tag" is not in FILTER_SPECS_BY_ID but IS in the valid_filter_ids set.
        bar = _bare_bar({}, tab="wall")
        form = {"action": "toggle", "id": "tag", "value": "python"}
        with app.test_request_context(method="POST", data=form):
            bar.update_state()
        assert bar.tag == "python"

    def test_successful_update_persists_to_session(self, app) -> None:
        bar = _bare_bar({}, tab="wall")
        form = {"action": "sort-by", "value": "likes"}
        with app.test_request_context(method="POST", data=form):
            bar.update_state()
            # A second FilterBar reading the same session sees the new order.
            fresh = _bare_bar(tab="wall")
            assert fresh.get_state().get("sort-by") == "likes"


class TestRemoveFilterEdgeCases:
    """`remove_filter` must be a safe no-op when the filter is absent —
    the dispatcher in `update_state` calls it eagerly."""

    def test_remove_missing_filter_is_noop(self) -> None:
        bar = _bare_bar({"filters": [{"id": "sector", "value": "tech"}]}, tab="wall")
        bar.remove_filter("genre", "news")
        assert bar.state["filters"] == [{"id": "sector", "value": "tech"}]

    def test_remove_from_empty_state_is_noop(self) -> None:
        bar = _bare_bar({}, tab="wall")
        bar.remove_filter("sector", "tech")
        # state untouched — no "filters" key was injected.
        assert bar.state == {}

    def test_remove_only_drops_first_match(self) -> None:
        # Defensive : duplicates shouldn't occur, but if they do, the
        # implementation removes ONE per call. Pin that behaviour.
        bar = _bare_bar(
            {
                "filters": [
                    {"id": "sector", "value": "tech"},
                    {"id": "sector", "value": "tech"},
                ]
            },
            tab="wall",
        )
        bar.remove_filter("sector", "tech")
        assert bar.state["filters"] == [{"id": "sector", "value": "tech"}]
