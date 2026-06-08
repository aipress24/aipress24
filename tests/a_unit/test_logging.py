# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Tests for `app.logging`.

`report_failure` is the bridge between silent `except` blocks that
swallow notification/email errors (so the surrounding state change
isn't undone) and Sentry. Without it, ops never learns SMTP is down
because nobody reads the logs. Ticket #0169."""

from __future__ import annotations

from unittest.mock import patch

from app.logging import report_failure


class TestReportFailure:
    def test_calls_sentry_capture_exception_with_the_passed_exc(self):
        exc = RuntimeError("smtp timeout")

        with patch("app.logging.sentry_sdk.capture_exception") as mock_capture:
            report_failure("revoke_partnership: email failed", exc)

        mock_capture.assert_called_once_with(exc)

    def test_also_emits_a_local_warning(self, capsys):
        exc = ValueError("nope")

        with patch("app.logging.sentry_sdk.capture_exception"):
            report_failure("test scope", exc)

        # `warn()` writes to stderr — the local log is preserved so a
        # dev tailing the terminal still sees the failure even with no
        # Sentry DSN configured.
        captured = capsys.readouterr()
        assert "test scope" in captured.err
        assert "nope" in captured.err

    def test_sentry_failure_does_not_propagate(self):
        """If Sentry itself raises (e.g. transport error), the helper
        must not re-raise — otherwise the original mail failure would
        be replaced by a Sentry failure and the caller's state would
        still be in jeopardy."""
        exc = RuntimeError("original")

        with patch(
            "app.logging.sentry_sdk.capture_exception",
            side_effect=RuntimeError("sentry down"),
        ):
            # Must not raise.
            report_failure("x", exc)
