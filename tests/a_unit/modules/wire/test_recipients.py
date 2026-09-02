# Copyright (c) 2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Parsing a hand-typed address list — 2026-09-02.

Two views each had their own version, and they did not split alike:
article sharing accepted a space as a separator and validated the
address shape, buying a gift consultation did not. The disagreement fell
on a **billed** path — one recipient more or less is one line more or
less on the invoice.
"""

from __future__ import annotations

import pytest

from app.modules.wire.services.recipients import parse_recipient_emails


class TestTheSeparators:
    """Comma, newline, space: interchangeably."""

    @pytest.mark.parametrize(
        "raw",
        [
            "a@b.com,c@d.com",
            "a@b.com\nc@d.com",
            "a@b.com c@d.com",
            "a@b.com , c@d.com",
            "a@b.com,\n  c@d.com\n",
        ],
    )
    def test_two_addresses_whatever_the_punctuation(self, raw) -> None:
        assert parse_recipient_emails(raw) == ["a@b.com", "c@d.com"]

    def test_the_space_split_in_one_version_and_not_the_other(self) -> None:
        """The case that diverged: on the purchase side, "a@b.com
        c@d.com" was a single string — invalid, and billed as one
        recipient."""
        assert len(parse_recipient_emails("a@b.com c@d.com")) == 2


class TestWhatIsDropped:
    @pytest.mark.parametrize(
        "raw", ["", "   ", "\n,\n", "not-an-address", "no@dot", "@b.com"]
    )
    def test_nothing_shaped_like_an_address_gets_through(self, raw) -> None:
        assert parse_recipient_emails(raw) == []

    def test_the_valid_survives_the_invalid(self) -> None:
        """One bad line must not take the whole list down with it."""
        assert parse_recipient_emails("good@ex.com, garbage, other@ex.com") == [
            "good@ex.com",
            "other@ex.com",
        ]


class TestNormalisation:
    def test_duplicates_count_once(self) -> None:
        """Otherwise the same recipient is billed twice."""
        assert parse_recipient_emails("A@B.com, a@b.com, a@B.COM") == ["a@b.com"]

    def test_case_does_not_matter(self) -> None:
        assert parse_recipient_emails("Jean.Dupont@Example.COM") == [
            "jean.dupont@example.com"
        ]

    def test_the_order_is_stable(self) -> None:
        """A `set` returned a different order from one call to the next —
        the invoice and the email did not list the same way."""
        raw = "z@ex.com, a@ex.com, m@ex.com"

        assert parse_recipient_emails(raw) == parse_recipient_emails(raw)
        assert parse_recipient_emails(raw) == ["a@ex.com", "m@ex.com", "z@ex.com"]
