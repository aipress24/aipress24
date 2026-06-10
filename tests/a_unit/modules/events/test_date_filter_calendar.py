# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Mock-free unit tests for `DateFilter` and `Calendar` helpers.

WHY these tests exist
---------------------
`src/app/modules/events/views/_common.py` exposes two pure value-object
helpers used by the events views :

- ``DateFilter`` parses a request-args dict (``{"day": ..., "month": ...}``)
  into Arrow boundary objects, then builds the corresponding WHERE clauses
  on a SQLAlchemy ``Select`` statement.
- ``Calendar.build_cells`` turns a list of events + a date range into a
  list of cell dicts ready to be rendered in either the sidebar mini
  calendar or the full calendar page.

Both classes are excellent candidates for pure-state tests :

- ``DateFilter`` only manipulates ``arrow.Arrow`` values and produces a
  SQLAlchemy ``Select`` whose WHERE clause can be inspected without a DB.
- ``Calendar.build_cells`` is a ``@staticmethod`` that accepts any object
  with ``start_datetime`` / ``end_datetime`` / ``id`` / ``title``
  attributes, so plain dataclass stubs are sufficient.

The ``Calendar.__init__`` constructor itself queries the DB via
``get_multi`` — that integration path is covered elsewhere. Here we
target only ``build_cells`` to lock down the day-iteration + grouping
logic.

The existing ``test_event_services.py`` covers EventListVM / EventDetailVM
view models, so we deliberately avoid duplicating that surface.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import arrow
import pytest
from arrow import Arrow
from sqlalchemy import Select, select

from app.modules.events.models import EventPost
from app.modules.events.views._common import Calendar, DateFilter

# ---------------------------------------------------------------------------
# Plain stubs (no Mock, no DB)
# ---------------------------------------------------------------------------


@dataclass
class _EventStub:
    """Minimal duck-typed stand-in for ``EventPost`` for ``build_cells``.

    ``build_cells`` only ever reads ``id``, ``title``, ``start_datetime``
    and ``end_datetime`` — anything else on the real model is irrelevant.
    """

    id: int
    title: str
    start_datetime: Arrow | None
    end_datetime: Arrow | None


def _ev(
    id_: int,
    title: str,
    start: str,
    end: str,
) -> _EventStub:
    """Build an event stub from ISO datetime strings."""
    return _EventStub(
        id=id_,
        title=title,
        start_datetime=arrow.get(start),
        end_datetime=arrow.get(end),
    )


# ---------------------------------------------------------------------------
# DateFilter — construction
# ---------------------------------------------------------------------------


class TestDateFilterConstruction:
    """Verify DateFilter parses request args into Arrow boundaries."""

    def test_day_argument_sets_filter_on_day(self) -> None:
        df = DateFilter({"day": "2024-06-15", "month": None})

        assert df.filter_on == "day"
        assert df.day is not None
        assert df.day.date() == arrow.get("2024-06-15").date()

    def test_day_argument_anchors_month_start_to_first(self) -> None:
        df = DateFilter({"day": "2024-06-15", "month": None})

        assert df.month_start.date() == arrow.get("2024-06-01").date()
        # month_end is exclusive — first day of the next month
        assert df.month_end.date() == arrow.get("2024-07-01").date()
        # month is aliased to month_start
        assert df.month == df.month_start

    def test_month_argument_sets_filter_on_month(self) -> None:
        df = DateFilter({"day": None, "month": "2024-08"})

        assert df.filter_on == "month"
        assert df.day is None
        assert df.month_start.date() == arrow.get("2024-08-01").date()
        assert df.month_end.date() == arrow.get("2024-09-01").date()

    def test_neither_argument_defaults_to_current_month(self) -> None:
        df = DateFilter({"day": None, "month": None})

        assert df.filter_on == ""
        assert df.day is None
        # month_start is the first of "today"'s month
        assert df.month_start.day == 1
        assert df.month_start.month == df.today.month
        assert df.month_start.year == df.today.year

    def test_today_is_midnight_today(self) -> None:
        df = DateFilter({"day": None, "month": None})

        # today must be normalised to the calendar date (no time component)
        assert df.today.hour == 0
        assert df.today.minute == 0
        assert df.today.second == 0
        assert df.today.date() == arrow.now().date()

    @pytest.mark.parametrize(
        ("month_arg", "expected_start", "expected_end"),
        [
            ("2024-01", "2024-01-01", "2024-02-01"),
            ("2024-12", "2024-12-01", "2025-01-01"),
            ("2025-02", "2025-02-01", "2025-03-01"),
        ],
    )
    def test_month_span_rolls_year(
        self,
        month_arg: str,
        expected_start: str,
        expected_end: str,
    ) -> None:
        df = DateFilter({"day": None, "month": month_arg})

        assert df.month_start.date() == arrow.get(expected_start).date()
        assert df.month_end.date() == arrow.get(expected_end).date()


# ---------------------------------------------------------------------------
# DateFilter — apply()
# ---------------------------------------------------------------------------


class TestDateFilterApply:
    """Verify DateFilter.apply mutates the SQLAlchemy Select as expected."""

    def _base_stmt(self) -> Select[Any]:
        return select(EventPost)

    def test_apply_returns_select(self) -> None:
        df = DateFilter({"day": "2024-06-15", "month": None})

        result = df.apply(self._base_stmt())

        assert isinstance(result, Select)

    def test_apply_day_adds_where_no_limit(self) -> None:
        df = DateFilter({"day": "2024-06-15", "month": None})

        stmt = df.apply(self._base_stmt())

        assert stmt.whereclause is not None
        assert stmt._limit is None  # type: ignore[attr-defined]
        # Day-mode produces a single AND of start<bound AND end>=bound
        rendered = str(stmt.whereclause)
        assert "start_datetime" in rendered
        assert "end_datetime" in rendered

    def test_apply_month_adds_where_no_limit(self) -> None:
        df = DateFilter({"day": None, "month": "2024-08"})

        stmt = df.apply(self._base_stmt())

        assert stmt.whereclause is not None
        assert stmt._limit is None  # type: ignore[attr-defined]

    def test_apply_default_branch_limits_to_30(self) -> None:
        df = DateFilter({"day": None, "month": None})

        stmt = df.apply(self._base_stmt())

        # Default upcoming-events view caps at 30 rows
        assert stmt._limit == 30  # type: ignore[attr-defined]
        assert stmt.whereclause is not None

    def test_apply_day_bound_values_are_inclusive_of_day(self) -> None:
        """The day filter must include events that start *on* the day."""
        df = DateFilter({"day": "2024-06-15", "month": None})

        stmt = df.apply(self._base_stmt())
        compiled = stmt.compile(compile_kwargs={"literal_binds": True})
        rendered = str(compiled).replace("\n", " ")

        # start_datetime is compared against the next day (exclusive upper)
        assert "2024-06-16" in rendered
        # end_datetime is compared against the day itself (inclusive lower)
        assert "2024-06-15" in rendered

    def test_apply_month_bound_values_use_month_window(self) -> None:
        df = DateFilter({"day": None, "month": "2024-08"})

        stmt = df.apply(self._base_stmt())
        compiled = stmt.compile(compile_kwargs={"literal_binds": True})
        rendered = str(compiled).replace("\n", " ")

        assert "2024-08-01" in rendered
        assert "2024-09-01" in rendered


# ---------------------------------------------------------------------------
# Calendar.build_cells — pure logic
# ---------------------------------------------------------------------------


class TestBuildCellsRange:
    """The day-iteration range must drop the end_date (exclusive end)."""

    def test_range_length_excludes_end_date(self) -> None:
        start = arrow.get("2024-06-01")
        end = arrow.get("2024-06-05")

        cells = Calendar.build_cells(
            events=[], start_date=start, end_date=end, today=start.date()
        )

        # 2024-06-01 .. 2024-06-04 inclusive, end excluded → 4 cells
        assert len(cells) == 4
        assert cells[0]["date"].date() == arrow.get("2024-06-01").date()
        assert cells[-1]["date"].date() == arrow.get("2024-06-04").date()

    def test_single_day_range_yields_no_cells(self) -> None:
        start = arrow.get("2024-06-01")
        # end == start → range has one element, sliced off → zero cells
        cells = Calendar.build_cells(
            events=[], start_date=start, end_date=start, today=start.date()
        )

        assert cells == []

    def test_is_today_flag_marks_only_today(self) -> None:
        start = arrow.get("2024-06-01")
        end = arrow.get("2024-06-05")
        today = arrow.get("2024-06-03").date()

        cells = Calendar.build_cells(
            events=[], start_date=start, end_date=end, today=today
        )

        today_cells = [c for c in cells if c["is_today"]]
        assert len(today_cells) == 1
        assert today_cells[0]["date"].date() == today


class TestBuildCellsSpanningCount:
    """include_details=False — counts events spanning each day."""

    def test_empty_events_yields_zero_counts(self) -> None:
        cells = Calendar.build_cells(
            events=[],
            start_date=arrow.get("2024-06-01"),
            end_date=arrow.get("2024-06-05"),
            today=arrow.get("2024-06-01").date(),
        )

        assert all(c["num_events"] == 0 for c in cells)
        assert all("events" not in c for c in cells)

    def test_single_day_event_counted_only_on_that_day(self) -> None:
        ev = _ev(1, "Lunch", "2024-06-02 12:00", "2024-06-02 13:00")

        cells = Calendar.build_cells(
            events=[ev],
            start_date=arrow.get("2024-06-01"),
            end_date=arrow.get("2024-06-05"),
            today=arrow.get("2024-06-01").date(),
        )

        counts = {c["date"].date(): c["num_events"] for c in cells}
        assert counts[arrow.get("2024-06-01").date()] == 0
        assert counts[arrow.get("2024-06-02").date()] == 1
        assert counts[arrow.get("2024-06-03").date()] == 0
        assert counts[arrow.get("2024-06-04").date()] == 0

    def test_multi_day_event_counted_on_every_spanned_day(self) -> None:
        ev = _ev(1, "Conference", "2024-06-01 09:00", "2024-06-04 18:00")

        cells = Calendar.build_cells(
            events=[ev],
            start_date=arrow.get("2024-06-01"),
            end_date=arrow.get("2024-06-05"),
            today=arrow.get("2024-06-01").date(),
        )

        assert all(c["num_events"] == 1 for c in cells)

    def test_overlapping_events_summed_per_day(self) -> None:
        events = [
            _ev(1, "Daily meet", "2024-06-02 09:00", "2024-06-02 10:00"),
            _ev(2, "Multi-day", "2024-06-01 09:00", "2024-06-04 18:00"),
        ]

        cells = Calendar.build_cells(
            events=events,
            start_date=arrow.get("2024-06-01"),
            end_date=arrow.get("2024-06-05"),
            today=arrow.get("2024-06-01").date(),
        )

        counts = {c["date"].date(): c["num_events"] for c in cells}
        assert counts[arrow.get("2024-06-01").date()] == 1
        assert counts[arrow.get("2024-06-02").date()] == 2
        assert counts[arrow.get("2024-06-03").date()] == 1
        assert counts[arrow.get("2024-06-04").date()] == 1

    def test_event_with_missing_datetimes_is_skipped(self) -> None:
        """Robustness — partially-set events should not crash counting."""
        events = [
            _EventStub(
                id=1,
                title="Half-set",
                start_datetime=None,
                end_datetime=arrow.get("2024-06-02"),
            ),
            _EventStub(
                id=2,
                title="Other",
                start_datetime=arrow.get("2024-06-02"),
                end_datetime=None,
            ),
        ]

        cells = Calendar.build_cells(
            events=events,
            start_date=arrow.get("2024-06-01"),
            end_date=arrow.get("2024-06-05"),
            today=arrow.get("2024-06-01").date(),
        )

        assert all(c["num_events"] == 0 for c in cells)


class TestBuildCellsDetails:
    """include_details=True — lists events that START on each day."""

    def test_empty_events_yields_empty_lists(self) -> None:
        cells = Calendar.build_cells(
            events=[],
            start_date=arrow.get("2024-06-01"),
            end_date=arrow.get("2024-06-05"),
            today=arrow.get("2024-06-01").date(),
            include_details=True,
        )

        assert all(c["events"] == [] for c in cells)
        assert all("num_events" not in c for c in cells)

    def test_event_listed_on_start_day_only(self) -> None:
        ev = _ev(1, "Talk", "2024-06-02 14:30", "2024-06-04 18:00")

        cells = Calendar.build_cells(
            events=[ev],
            start_date=arrow.get("2024-06-01"),
            end_date=arrow.get("2024-06-05"),
            today=arrow.get("2024-06-01").date(),
            include_details=True,
        )

        listings = {c["date"].date(): c["events"] for c in cells}
        assert listings[arrow.get("2024-06-01").date()] == []
        assert listings[arrow.get("2024-06-02").date()] == [
            {
                "id": 1,
                "title": "Talk",
                "time": "14:30",
                "datetime": "2024-06-02T14:30",
            }
        ]
        # Even though the event spans to 06-04, details only show on start day
        assert listings[arrow.get("2024-06-03").date()] == []
        assert listings[arrow.get("2024-06-04").date()] == []

    def test_time_is_hh_mm_no_seconds(self) -> None:
        """Bug 0131 — time format must be HH:MM (not HH:MM:SS)."""
        ev = _ev(1, "Sharp", "2024-06-02 09:05:42", "2024-06-02 10:00")

        cells = Calendar.build_cells(
            events=[ev],
            start_date=arrow.get("2024-06-02"),
            end_date=arrow.get("2024-06-03"),
            today=arrow.get("2024-06-02").date(),
            include_details=True,
        )

        [day_cell] = cells
        [entry] = day_cell["events"]
        assert entry["time"] == "09:05"
        # No seconds component at all
        assert ":42" not in entry["time"]

    def test_datetime_iso_format_lacks_timezone(self) -> None:
        """Bug 0131 — datetime must be HTML5 <time>-friendly."""
        ev = _ev(1, "Sharp", "2024-06-02 09:05", "2024-06-02 10:00")

        cells = Calendar.build_cells(
            events=[ev],
            start_date=arrow.get("2024-06-02"),
            end_date=arrow.get("2024-06-03"),
            today=arrow.get("2024-06-02").date(),
            include_details=True,
        )

        [day_cell] = cells
        [entry] = day_cell["events"]
        assert entry["datetime"] == "2024-06-02T09:05"

    def test_multiple_events_on_same_start_day_are_all_listed(self) -> None:
        events = [
            _ev(1, "Morning", "2024-06-02 09:00", "2024-06-02 10:00"),
            _ev(2, "Afternoon", "2024-06-02 14:00", "2024-06-02 15:00"),
            _ev(3, "Other day", "2024-06-03 09:00", "2024-06-03 10:00"),
        ]

        cells = Calendar.build_cells(
            events=events,
            start_date=arrow.get("2024-06-02"),
            end_date=arrow.get("2024-06-04"),
            today=arrow.get("2024-06-02").date(),
            include_details=True,
        )

        listings = {c["date"].date(): c["events"] for c in cells}
        ids_day2 = [e["id"] for e in listings[arrow.get("2024-06-02").date()]]
        ids_day3 = [e["id"] for e in listings[arrow.get("2024-06-03").date()]]
        assert ids_day2 == [1, 2]
        assert ids_day3 == [3]

    def test_event_with_missing_start_is_skipped(self) -> None:
        ev = _EventStub(
            id=1,
            title="No-start",
            start_datetime=None,
            end_datetime=arrow.get("2024-06-02"),
        )

        cells = Calendar.build_cells(
            events=[ev],
            start_date=arrow.get("2024-06-02"),
            end_date=arrow.get("2024-06-03"),
            today=arrow.get("2024-06-02").date(),
            include_details=True,
        )

        assert cells[0]["events"] == []
