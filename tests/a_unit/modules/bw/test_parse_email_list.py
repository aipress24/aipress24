# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Unit tests for `parse_email_list` in
`app.modules.bw.bw_activation.bw_invitation`.

The BW admin UI exposes a textarea where the BW owner pastes the list
of emails to be (re)invited as Manager or PR Manager. The textarea
is intentionally loose : the user can paste one email per line,
comma-separated, space-separated, mixed-case, with leading/trailing
whitespace.

This helper normalises that mess into a canonical set the
diff-against-current-pending logic can compare to. Pin the contract
so a future « stricter parser » regression doesn't silently drop
legitimate emails.
"""

from __future__ import annotations

from app.modules.bw.bw_activation.bw_invitation import parse_email_list


class TestParseEmailList:
    def test_single_email_one_per_line(self):
        assert parse_email_list("foo@example.com") == {"foo@example.com"}

    def test_two_emails_one_per_line(self):
        result = parse_email_list("foo@example.com\nbar@example.com")
        assert result == {"foo@example.com", "bar@example.com"}

    def test_space_separated(self):
        """Pasted from a Word doc / messenger : space-separated. Pin
        the loose parsing — a future « only newlines » regression
        would silently drop emails."""
        result = parse_email_list("foo@example.com bar@example.com")
        assert result == {"foo@example.com", "bar@example.com"}

    def test_mixed_case_normalised_to_lower(self):
        """Erick #0157 stored emails case-insensitively. Pin the
        normalisation."""
        result = parse_email_list("Foo@Example.COM\nbar@EXAMPLE.com")
        assert result == {"foo@example.com", "bar@example.com"}

    def test_trims_whitespace_around_each_email(self):
        """Strips per-token whitespace — pasted from a poorly-
        formatted source. Pin."""
        result = parse_email_list("  foo@example.com  \n  bar@example.com  ")
        assert result == {"foo@example.com", "bar@example.com"}

    def test_duplicates_deduplicated(self):
        """Set semantics : same email twice → one entry. Pin so the
        admin's flash count doesn't double-count a typo."""
        result = parse_email_list("foo@example.com\nfoo@example.com")
        assert result == {"foo@example.com"}

    def test_duplicates_case_insensitive(self):
        """`Foo@…` and `foo@…` are the same — after lowercasing,
        deduplication catches them."""
        result = parse_email_list("Foo@example.com\nfoo@EXAMPLE.com")
        assert result == {"foo@example.com"}

    def test_empty_string_returns_empty_set(self):
        assert parse_email_list("") == set()

    def test_none_returns_empty_set(self):
        """A None payload (textarea unfilled, defensive coercion)
        must NOT crash — the empty list IS the « no invitations »
        signal the caller diff-against-current logic handles."""
        assert parse_email_list(None) == set()

    def test_only_whitespace_returns_empty(self):
        """A whitespace-only textarea is honest-to-goodness empty."""
        assert parse_email_list("   \n\n\t  ") == set()

    def test_tab_separated(self):
        """Pasted from a spreadsheet : tab-separated. `str.split()`
        treats tabs as whitespace, so it works."""
        result = parse_email_list("foo@example.com\tbar@example.com")
        assert result == {"foo@example.com", "bar@example.com"}

    def test_mixed_separators(self):
        """Real-world worst case : the user's clipboard has a mix
        of spaces, newlines, and tabs."""
        raw = "foo@example.com \n bar@example.com\tbaz@example.com"
        result = parse_email_list(raw)
        assert result == {
            "foo@example.com",
            "bar@example.com",
            "baz@example.com",
        }

    def test_does_not_validate_email_shape(self):
        """The parser doesn't enforce RFC-compliant emails — that's
        the invite_fn's job (it tries to find a User by email). Pin
        so a future « let's validate shape here too » regression
        doesn't accidentally tighten the contract."""
        result = parse_email_list("not-an-email\nfoo@example.com")
        assert result == {"not-an-email", "foo@example.com"}

    def test_preserves_dot_and_plus_addressing(self):
        """Gmail-style `+` tags and dotted aliases must round-trip
        verbatim. Pin so a future regex strip doesn't mangle them."""
        result = parse_email_list("foo+tag@example.com\nbar.baz@example.com")
        assert result == {"foo+tag@example.com", "bar.baz@example.com"}

    def test_returns_set_type(self):
        """The caller uses set operations (`in`, set difference).
        Pin the return type so a future list-based refactor doesn't
        silently change perf characteristics."""
        result = parse_email_list("foo@example.com")
        assert isinstance(result, set)
