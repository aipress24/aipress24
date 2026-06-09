# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Unit tests for `app.modules.wire.services.article_access`.

Exists to cover the paywall rule table + the HTML truncation helpers
without spinning up a database or mocking SQLAlchemy. The verdict
function `user_can_read_full` accepts injected lookup callables
(default-arg DI) so tests pass plain Python callables instead of
patching `db.session`. A pure `_decide_can_read_full` core captures
the rule table as a precedence ladder and is exercised in isolation.

These tests intentionally use duck-typed `_User` / `_Post` stand-ins
rather than the SQLAlchemy ORM classes — they only read attributes
the SUT actually touches (`is_anonymous`, `id`, `owner_id`), so the
ORM machinery is not needed.
"""

from __future__ import annotations

import pytest

from app.enums import RoleEnum
from app.modules.wire.services.article_access import (
    _cut_on_word_boundary,
    _decide_can_read_full,
    truncate_body,
    user_can_read_full,
)


class _User:
    """Duck-typed stand-in for `flask_security`'s `User`. Only the
    attributes the SUT reads are populated."""

    def __init__(self, *, user_id: int | None, is_anonymous: bool = False) -> None:
        self.id = user_id
        self.is_anonymous = is_anonymous


class _Post:
    """Duck-typed stand-in for `wire.models.Post`."""

    def __init__(self, *, post_id: int, owner_id: int) -> None:
        self.id = post_id
        self.owner_id = owner_id


def _never_paid(_user_id: int, _post_id: int) -> bool:
    return False


def _always_paid(_user_id: int, _post_id: int) -> bool:
    return True


def _never_gifted(_user_id: int, _post_id: int) -> bool:
    return False


def _always_gifted(_user_id: int, _post_id: int) -> bool:
    return True


def _no_role(_user: object, _role: str) -> bool:
    return False


def _admin_role(_user: object, role: str) -> bool:
    return role == RoleEnum.ADMIN.name


class TestDecideCanReadFull:
    """Pure rule table: precedence is anonymous < author < admin <
    paid < gift, with the first matching rule winning."""

    def test_anonymous_blocks_even_if_all_other_flags_true(self) -> None:
        assert (
            _decide_can_read_full(
                is_anonymous=True,
                is_author=True,
                is_admin=True,
                has_paid=True,
                has_gift=True,
            )
            is False
        )

    def test_author_wins_over_missing_purchases(self) -> None:
        assert (
            _decide_can_read_full(
                is_anonymous=False,
                is_author=True,
                is_admin=False,
                has_paid=False,
                has_gift=False,
            )
            is True
        )

    def test_admin_unlocks_without_purchase(self) -> None:
        assert (
            _decide_can_read_full(
                is_anonymous=False,
                is_author=False,
                is_admin=True,
                has_paid=False,
                has_gift=False,
            )
            is True
        )

    def test_paid_purchase_unlocks(self) -> None:
        assert (
            _decide_can_read_full(
                is_anonymous=False,
                is_author=False,
                is_admin=False,
                has_paid=True,
                has_gift=False,
            )
            is True
        )

    def test_gift_unlocks(self) -> None:
        assert (
            _decide_can_read_full(
                is_anonymous=False,
                is_author=False,
                is_admin=False,
                has_paid=False,
                has_gift=True,
            )
            is True
        )

    def test_nothing_matches_returns_false(self) -> None:
        assert (
            _decide_can_read_full(
                is_anonymous=False,
                is_author=False,
                is_admin=False,
                has_paid=False,
                has_gift=False,
            )
            is False
        )


class TestUserCanReadFullGuards:
    """The shell wraps the pure core with anonymous / author checks
    that short-circuit before any role or DB lookup runs."""

    def test_none_user_returns_false(self) -> None:
        post = _Post(post_id=1, owner_id=42)
        assert (
            user_can_read_full(
                None,
                post,  # type: ignore[arg-type]
                role_checker=_no_role,
                paid_lookup=_never_paid,
                gift_lookup=_never_gifted,
            )
            is False
        )

    def test_anonymous_user_returns_false(self) -> None:
        anon = _User(user_id=None, is_anonymous=True)
        post = _Post(post_id=1, owner_id=42)
        assert (
            user_can_read_full(
                anon,  # type: ignore[arg-type]
                post,  # type: ignore[arg-type]
                role_checker=_no_role,
                paid_lookup=_never_paid,
                gift_lookup=_never_gifted,
            )
            is False
        )

    def test_author_short_circuits_without_invoking_lookups(self) -> None:
        """Author check happens before the role or DB lookups; passing
        callables that would raise proves they are never called."""

        def boom(*_args: object, **_kwargs: object) -> bool:
            msg = "lookup should not run for the author"
            raise AssertionError(msg)

        author = _User(user_id=42, is_anonymous=False)
        post = _Post(post_id=1, owner_id=42)
        assert (
            user_can_read_full(
                author,  # type: ignore[arg-type]
                post,  # type: ignore[arg-type]
                role_checker=boom,
                paid_lookup=boom,
                gift_lookup=boom,
            )
            is True
        )


class TestUserCanReadFullVerdicts:
    """End-to-end verdicts on the shell with stubbed collaborators —
    one parametric matrix per (admin, paid, gift, expected)."""

    @pytest.mark.parametrize(
        ("is_admin", "has_paid", "has_gift", "expected"),
        [
            (False, False, False, False),
            (True, False, False, True),
            (False, True, False, True),
            (False, False, True, True),
            (True, True, True, True),
        ],
    )
    def test_verdict_matches_rule_table(
        self,
        *,
        is_admin: bool,
        has_paid: bool,
        has_gift: bool,
        expected: bool,
    ) -> None:
        reader = _User(user_id=7, is_anonymous=False)
        post = _Post(post_id=99, owner_id=42)

        role_checker = _admin_role if is_admin else _no_role
        paid_lookup = _always_paid if has_paid else _never_paid
        gift_lookup = _always_gifted if has_gift else _never_gifted

        result = user_can_read_full(
            reader,  # type: ignore[arg-type]
            post,  # type: ignore[arg-type]
            role_checker=role_checker,
            paid_lookup=paid_lookup,
            gift_lookup=gift_lookup,
        )
        assert result is expected

    def test_lookups_receive_user_and_post_ids(self) -> None:
        """Sanity: the shell threads (user.id, post.id) — not the
        objects themselves — into the injected lookups."""
        calls: list[tuple[int, int]] = []

        def record_paid(user_id: int, post_id: int) -> bool:
            calls.append(("paid", user_id, post_id))  # type: ignore[arg-type]
            return False

        def record_gift(user_id: int, post_id: int) -> bool:
            calls.append(("gift", user_id, post_id))  # type: ignore[arg-type]
            return False

        reader = _User(user_id=7, is_anonymous=False)
        post = _Post(post_id=99, owner_id=42)
        user_can_read_full(
            reader,  # type: ignore[arg-type]
            post,  # type: ignore[arg-type]
            role_checker=_no_role,
            paid_lookup=record_paid,
            gift_lookup=record_gift,
        )
        assert calls == [("paid", 7, 99), ("gift", 7, 99)]


class TestTruncateBody:
    """`truncate_body` preserves well-formed HTML up to `limit`
    visible characters and adds an ellipsis when it cuts."""

    def test_empty_input_returns_empty_string(self) -> None:
        assert truncate_body("") == ""

    def test_short_html_is_returned_verbatim(self) -> None:
        html = "<p>short body</p>"
        assert truncate_body(html, limit=300) == html

    def test_long_html_is_truncated_with_ellipsis(self) -> None:
        html = "<p>" + ("abcdefgh " * 200) + "</p>"
        truncated = truncate_body(html, limit=100)
        assert truncated.startswith("<p>")
        assert truncated.endswith("</p>")
        assert "…" in truncated
        assert len(truncated) < len(html)

    def test_inner_tags_are_preserved(self) -> None:
        html = "<p>Start <strong>bold</strong> and more text here.</p>"
        truncated = truncate_body(html, limit=20)
        # Tag structure stays closed regardless of where we cut.
        assert truncated.startswith("<p>")
        assert truncated.endswith("</p>")
        assert "<strong>" in truncated


class TestCutOnWordBoundary:
    """Internal helper used by `truncate_body` — pure on str."""

    def test_returns_text_unchanged_when_limit_exceeds_length(self) -> None:
        assert _cut_on_word_boundary("hello", 99) == "hello"

    def test_cuts_at_last_whitespace_within_limit(self) -> None:
        # "the quick brown fox" with limit=15 → keep "the quick brown"
        # (whitespace at index 15 is within the > 0.6 * limit window).
        text = "the quick brown fox"
        cut = _cut_on_word_boundary(text, 15)
        assert cut == "the quick brown"

    def test_falls_back_to_hard_cut_when_whitespace_is_too_early(self) -> None:
        # No whitespace at all → no boundary to honour, hard cut wins.
        text = "abcdefghijklmnop"
        cut = _cut_on_word_boundary(text, 10)
        assert cut == "abcdefghij"

    def test_hard_cut_when_only_whitespace_is_below_threshold(self) -> None:
        # Whitespace at index 1 with limit=10 → 1 is not > 6, so the
        # function refuses to trim too aggressively and returns the
        # raw slice up to `limit`.
        text = "a bcdefghijklmnop"
        cut = _cut_on_word_boundary(text, 10)
        assert cut == "a bcdefghi"
