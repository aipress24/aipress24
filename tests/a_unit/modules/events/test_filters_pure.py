# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Additional unit tests for events/views/_filters.py.

These tests complement tests/a_unit/modules/events/test_filters.py by
covering pure helpers and code paths that were not yet exercised:

- constant invariants (FILTER_SPECS_BY_ID, FILTER_TAG_LABEL alignment,
  SORTER_OPTIONS shape)
- sorter property output
- active_filters with a label_function (state-based)
- active_filters when the filter id is unknown to FILTER_SPECS_BY_ID
- remove_filter no-ops on missing entries
- tag property selecting the right entry across mixed filters
- set_tag via a no-op save_state stand-in (no Flask session)

All tests are mock-free: they either drive plain Python state, or use a
small ``_FilterBarStub`` subclass that overrides ``save_state`` with a
canned no-op. This follows the project rule of "prefer stubs over
mocks" and verifies tangible state instead of interactions.
"""

from __future__ import annotations

import pytest

from app.modules.events.views._filters import (
    FILTER_SPECS,
    FILTER_SPECS_BY_ID,
    FILTER_TAG_LABEL,
    SORTER_OPTIONS,
    FilterBar,
)

# ---------------------------------------------------------------------------
# Test helpers (stubs, not mocks)
# ---------------------------------------------------------------------------


class _FilterBarStub(FilterBar):
    """Stand-in FilterBar that replaces session I/O with in-memory state.

    The production __init__ reads from ``flask.session`` which requires a
    Flask request context. We bypass __init__ and provide a no-op
    ``save_state`` so the pure state-mutation paths can be exercised.
    """

    def __init__(self, state: dict | None = None) -> None:
        # Skip FilterBar.__init__ on purpose; it touches Flask globals.
        self.state = state if state is not None else {}
        self.filters: list[dict] = []
        self.saves = 0

    def save_state(self) -> None:
        # Tangible side effect: count calls without using mocks.
        self.saves += 1


def _make_bar(state: dict | None = None) -> _FilterBarStub:
    return _FilterBarStub(state)


# ---------------------------------------------------------------------------
# Constant invariants
# ---------------------------------------------------------------------------


class TestFilterConstantsInvariants:
    """Cross-checks between FILTER_SPECS / FILTER_SPECS_BY_ID / TAG labels."""

    def test_filter_specs_by_id_keys_match_filter_specs(self) -> None:
        expected = {spec["id"] for spec in FILTER_SPECS}
        assert set(FILTER_SPECS_BY_ID.keys()) == expected

    def test_filter_specs_by_id_values_are_specs(self) -> None:
        for spec_id, spec in FILTER_SPECS_BY_ID.items():
            assert spec["id"] == spec_id
            assert "label" in spec
            assert "column" in spec

    def test_filter_tag_label_keys_are_filter_ids(self) -> None:
        spec_ids = {spec["id"] for spec in FILTER_SPECS}
        # Every tag label must reference a real filter spec id.
        assert set(FILTER_TAG_LABEL.keys()) <= spec_ids

    def test_filter_tag_label_values_are_non_empty_strings(self) -> None:
        for tag in FILTER_TAG_LABEL.values():
            assert isinstance(tag, str)
            assert tag

    def test_sorter_options_first_is_date(self) -> None:
        assert SORTER_OPTIONS[0][0] == "date"

    @pytest.mark.parametrize(("value", "label"), SORTER_OPTIONS)
    def test_sorter_option_pair_shape(self, value: str, label: str) -> None:
        assert value and label

    def test_pays_zip_ville_has_label_function(self) -> None:
        spec = FILTER_SPECS_BY_ID["pays_zip_ville"]
        assert callable(spec.get("label_function"))


# ---------------------------------------------------------------------------
# sorter property
# ---------------------------------------------------------------------------


class TestSorterProperty:
    def test_sorter_returns_all_options(self) -> None:
        bar = _make_bar()
        opts = bar.sorter["options"]
        assert len(opts) == len(SORTER_OPTIONS)

    def test_sorter_default_selected_is_date(self) -> None:
        bar = _make_bar()
        opts = bar.sorter["options"]
        selected = [o for o in opts if o["selected"]]
        assert len(selected) == 1
        assert selected[0]["value"] == "date"

    def test_sorter_selected_follows_state(self) -> None:
        bar = _make_bar({"sort-by": "views"})
        opts = bar.sorter["options"]
        selected = [o for o in opts if o["selected"]]
        assert [s["value"] for s in selected] == ["views"]

    def test_sorter_option_keys(self) -> None:
        bar = _make_bar()
        for opt in bar.sorter["options"]:
            assert set(opt.keys()) == {"value", "label", "selected"}


# ---------------------------------------------------------------------------
# active_filters edge cases
# ---------------------------------------------------------------------------


class TestActiveFiltersEdges:
    def test_active_filters_empty_state(self) -> None:
        bar = _make_bar()
        assert bar.active_filters == []

    def test_active_filters_uses_label_function(self) -> None:
        """When a spec defines ``label_function``, label is transformed.

        We swap the label_function for the ``pays_zip_ville`` spec with a
        plain Python callable for the duration of the test. Because the
        spec dict is module-level, we restore it afterwards.
        """
        spec = FILTER_SPECS_BY_ID["pays_zip_ville"]
        original = spec.get("label_function")
        spec["label_function"] = lambda code: f"<{code}>"
        try:
            bar = _make_bar(
                {"filters": [{"id": "pays_zip_ville", "value": "FR"}]}
            )
            active = bar.active_filters
        finally:
            spec["label_function"] = original

        assert len(active) == 1
        entry = active[0]
        assert entry["id"] == "pays_zip_ville"
        assert entry["value"] == "FR"
        assert entry["label"] == "<FR>"
        assert entry["tag_label"] == FILTER_TAG_LABEL["pays_zip_ville"]
        assert entry["type"] == "selector"

    def test_active_filters_unknown_id_has_no_tag_label(self) -> None:
        bar = _make_bar({"filters": [{"id": "tag", "value": "python"}]})
        # 'tag' is a runtime filter id with no entry in FILTER_SPECS_BY_ID.
        active = bar.active_filters
        assert len(active) == 1
        assert active[0]["id"] == "tag"
        assert active[0]["tag_label"] == ""
        # No label_function => label is the raw value.
        assert active[0]["label"] == "python"

    def test_active_filters_preserves_order(self) -> None:
        state = {
            "filters": [
                {"id": "sector", "value": "tech"},
                {"id": "genre", "value": "conf"},
                {"id": "ville", "value": "Paris"},
            ]
        }
        bar = _make_bar(state)
        ids = [entry["id"] for entry in bar.active_filters]
        assert ids == ["sector", "genre", "ville"]


# ---------------------------------------------------------------------------
# tag property with mixed filters
# ---------------------------------------------------------------------------


class TestTagPropertyMixed:
    def test_tag_returns_first_tag_when_mixed(self) -> None:
        state = {
            "filters": [
                {"id": "genre", "value": "conf"},
                {"id": "tag", "value": "python"},
                {"id": "tag", "value": "django"},
            ]
        }
        bar = _make_bar(state)
        # The implementation returns the FIRST tag filter found.
        assert bar.tag == "python"

    def test_tag_ignores_non_tag_filters(self) -> None:
        bar = _make_bar({"filters": [{"id": "genre", "value": "conf"}]})
        assert bar.tag == ""


# ---------------------------------------------------------------------------
# remove_filter no-ops and add/remove cycles
# ---------------------------------------------------------------------------


class TestRemoveFilterNoOps:
    def test_remove_filter_missing_id_is_noop(self) -> None:
        state = {"filters": [{"id": "genre", "value": "conf"}]}
        bar = _make_bar(state)
        bar.remove_filter("sector", "tech")
        assert bar.state["filters"] == [{"id": "genre", "value": "conf"}]

    def test_remove_filter_wrong_value_is_noop(self) -> None:
        state = {"filters": [{"id": "genre", "value": "conf"}]}
        bar = _make_bar(state)
        bar.remove_filter("genre", "other")
        assert bar.state["filters"] == [{"id": "genre", "value": "conf"}]

    def test_remove_filter_empty_state_is_noop(self) -> None:
        bar = _make_bar()
        # No 'filters' key at all -> still safe.
        bar.remove_filter("genre", "conf")
        assert bar.state.get("filters", []) == []

    def test_remove_filter_only_removes_first_match(self) -> None:
        state = {
            "filters": [
                {"id": "genre", "value": "conf"},
                {"id": "genre", "value": "conf"},
            ]
        }
        bar = _make_bar(state)
        bar.remove_filter("genre", "conf")
        # Implementation breaks after the first match.
        assert bar.state["filters"] == [{"id": "genre", "value": "conf"}]


class TestAddRemoveCycles:
    def test_add_then_remove_yields_empty(self) -> None:
        bar = _make_bar()
        bar.add_filter("genre", "conf")
        bar.remove_filter("genre", "conf")
        assert bar.state["filters"] == []

    def test_toggle_twice_is_identity(self) -> None:
        bar = _make_bar()
        bar.toggle_filter("sector", "tech")
        bar.toggle_filter("sector", "tech")
        assert bar.has_filter("sector", "tech") is False

    def test_add_same_value_twice_creates_duplicate(self) -> None:
        # Documenting current behaviour: add_filter does NOT dedupe.
        bar = _make_bar()
        bar.add_filter("genre", "conf")
        bar.add_filter("genre", "conf")
        assert len(bar.state["filters"]) == 2


# ---------------------------------------------------------------------------
# set_tag / reset (using stub save_state)
# ---------------------------------------------------------------------------


class TestSetTagAndReset:
    def test_set_tag_adds_tag_filter_and_saves(self) -> None:
        bar = _make_bar()
        bar.set_tag("python")
        assert bar.state["filters"] == [{"id": "tag", "value": "python"}]
        assert bar.saves == 1

    def test_set_tag_then_tag_property(self) -> None:
        bar = _make_bar()
        bar.set_tag("django")
        assert bar.tag == "django"

    def test_reset_clears_state_and_saves(self) -> None:
        bar = _make_bar(
            {
                "filters": [{"id": "genre", "value": "conf"}],
                "sort-by": "views",
            }
        )
        bar.reset()
        assert bar.state == {}
        assert bar.saves == 1

    def test_reset_then_sort_order_defaults(self) -> None:
        bar = _make_bar({"sort-by": "likes"})
        bar.reset()
        assert bar.sort_order == "date"
