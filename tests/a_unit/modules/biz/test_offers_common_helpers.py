# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Unit tests for the pure helpers in
`app.modules.biz.views._offers_common`.

These two-liner helpers are called by every Mission / Project / Job
offer publish-form handler. They're small but pinning them stops the
classic regressions :

- `euros_to_cents` : misread the storage unit (cents vs euros) and
  the budget on every new offer is off by 100x. The recent code
  review on `modules/wire` surfaced exactly this kind of confusion
  with Stripe's HT vs TTC. Pin the contract.

- `date_to_datetime` : the WTForms `DateField` parses to a
  `datetime.date` ; SQLAlchemy needs `datetime.datetime`. The naive
  combine-with-midnight is timezone-naive — that's deliberate
  (the column is stored in UTC by SQLAlchemy / Postgres). Don't
  silently introduce a tzinfo without explicit handling.
"""

from __future__ import annotations

from datetime import date, datetime, time

from app.modules.biz.models import ApplicationStatus
from app.modules.biz.views._offers_common import (
    date_to_datetime,
    euros_to_cents,
    normalise_application_message,
    should_transition_to,
)


class TestEurosToCents:
    def test_typical_amount(self):
        assert euros_to_cents(100) == 10_000

    def test_zero_amount(self):
        """Zero must stay zero — not a special case, not None.
        Pin so a future `if not value: return None` regression is
        caught immediately."""
        assert euros_to_cents(0) == 0

    def test_negative_amount_preserved(self):
        """Negative budgets shouldn't normally land here but the
        helper doesn't validate — it leaves the policy to the form."""
        assert euros_to_cents(-50) == -5000

    def test_large_amount(self):
        """Stripe upper bound is around 999 999 99 cents (~10 M €).
        We sit well under, but pin one big value to catch overflow
        bugs if cents ever migrates to a smaller int type."""
        assert euros_to_cents(50_000) == 5_000_000

    def test_none_returns_none(self):
        """The DateField / IntegerField returns None when the user
        leaves the field empty. `None → None` preserves the optional
        column semantics on the model."""
        assert euros_to_cents(None) is None


class TestDateToDatetime:
    def test_typical_date(self):
        """A `date` becomes a `datetime` at midnight on the same day —
        no timezone information attached (UTC-naive)."""
        d = date(2026, 6, 9)
        result = date_to_datetime(d)
        assert isinstance(result, datetime)
        assert result.year == 2026
        assert result.month == 6
        assert result.day == 9
        assert result.time() == time(0, 0, 0)

    def test_result_is_timezone_naive(self):
        """The combine-with-midnight produces a naive datetime — by
        design, since Postgres/SQLAlchemy handles tz on the column.
        Pin so an accidental `tzinfo=UTC` doesn't silently change
        the stored value."""
        result = date_to_datetime(date(2026, 6, 9))
        assert result is not None
        assert result.tzinfo is None

    def test_none_returns_none(self):
        """Optional date field : empty input means no deadline."""
        assert date_to_datetime(None) is None

    def test_datetime_input_combines_to_midnight(self):
        """Edge case : `datetime.combine(d, time)` works on `date`
        OR `datetime` (subclass). If someone passes a full datetime
        we still get midnight on its date component — pin so this
        non-obvious behaviour is documented."""
        # The intent of these tests is *to verify naive datetimes* —
        # adding a tzinfo would defeat the assertion. Ruff's DTZ001
        # is suppressed here on purpose.
        dt = datetime(2026, 6, 9, 14, 30, 0)  # noqa: DTZ001
        result = date_to_datetime(dt)
        assert result is not None
        assert result == datetime(2026, 6, 9, 0, 0, 0)  # noqa: DTZ001


class TestNormaliseApplicationMessage:
    """Pinning the contract of the candidature `message` field
    normalisation. Called by `handle_apply` on every POST."""

    def test_none_returns_empty(self):
        assert normalise_application_message(None) == ""

    def test_empty_string_returns_empty(self):
        assert normalise_application_message("") == ""

    def test_strips_leading_and_trailing_whitespace(self):
        """Tab/newline at the edges (from copy-paste) get cleaned."""
        assert normalise_application_message("  hello  ") == "hello"
        assert normalise_application_message("\n\nhello\n") == "hello"
        assert normalise_application_message("\thello\t") == "hello"

    def test_internal_whitespace_preserved(self):
        """The candidate's message body keeps its internal spacing.
        Pin so a future « collapse internal spaces » regression
        doesn't ruin formatting."""
        assert (
            normalise_application_message("Hello\n\nI'm interested.\nBest")
            == "Hello\n\nI'm interested.\nBest"
        )

    def test_only_whitespace_returns_empty(self):
        """Whitespace-only input → empty string. The dashboard
        renders a meaningful empty cell instead of a blank-looking
        row that's actually full of spaces."""
        assert normalise_application_message("    ") == ""
        assert normalise_application_message("\n\n\t") == ""

    def test_long_message_preserved(self):
        """No truncation — message length is the form validator's
        responsibility, not the normaliser's."""
        long_msg = "x" * 5000
        assert normalise_application_message(long_msg) == long_msg


class TestShouldTransitionTo:
    """Pure predicate driving the « should we notify? » branch in
    `update_application_status`. Pinning prevents the « double-notify
    on a re-press » regression."""

    def test_pending_to_selected_transitions(self):
        assert (
            should_transition_to(ApplicationStatus.PENDING, ApplicationStatus.SELECTED)
            is True
        )

    def test_pending_to_rejected_transitions(self):
        assert (
            should_transition_to(ApplicationStatus.PENDING, ApplicationStatus.REJECTED)
            is True
        )

    def test_selected_to_rejected_transitions(self):
        """The emitter changing their mind : SELECTED → REJECTED
        IS a transition and DOES fire a notification. Pin so a
        future « only from PENDING » regression doesn't silently
        skip the reject mail."""
        assert (
            should_transition_to(ApplicationStatus.SELECTED, ApplicationStatus.REJECTED)
            is True
        )

    def test_rejected_to_selected_transitions(self):
        """Inverse — the emitter changes their mind the other way."""
        assert (
            should_transition_to(ApplicationStatus.REJECTED, ApplicationStatus.SELECTED)
            is True
        )

    def test_same_status_does_not_transition(self):
        """The whole point : a re-press on an already-SELECTED row
        must NOT trigger a second notification."""
        assert (
            should_transition_to(ApplicationStatus.SELECTED, ApplicationStatus.SELECTED)
            is False
        )
        assert (
            should_transition_to(ApplicationStatus.REJECTED, ApplicationStatus.REJECTED)
            is False
        )
        assert (
            should_transition_to(ApplicationStatus.PENDING, ApplicationStatus.PENDING)
            is False
        )
