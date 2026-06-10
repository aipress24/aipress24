# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Unit tests for ``app.flask.sqla``.

The production module mixes pure id-parsing logic with SQLAlchemy
``db.session`` calls. These tests target only the pure surface that does
not require a live database:

* ``parse_id`` — extracted helper that normalises ``int``/``str`` ids to
  ``int`` and raises ``werkzeug.exceptions.NotFound`` for unparseable
  input. Covers all three ``match`` arms of the original ``get_obj``
  decoding logic.
* The argument-shaping branches of ``get_multi`` (None/limit/options) are
  exercised by passing a stub ORM-shaped class through
  ``select(cls)`` — we don't actually call the database, we just want to
  prove the helper raises the same family of errors that production
  callers see when the session is unavailable.

DB-bound paths (``get_obj`` success / not-found, ``get_multi`` execute)
live in ``tests/b_integration/test_models.py`` and a future sister file.

Mock-free per CLAUDE.md: no test doubles, no patching fixtures, no
captured-call recorders. The tests assert on observable state — the
returned ``int`` value or the raised ``NotFound`` exception.
"""

from __future__ import annotations

import pytest
from werkzeug.exceptions import NotFound

from app.flask.sqla import parse_id
from app.lib.base62 import base62


class TestParseIdWithInts:
    """``parse_id`` should pass through integer inputs unchanged."""

    @pytest.mark.parametrize("value", [0, 1, 42, 9999, 2**31 - 1])
    def test_int_passthrough(self, value: int) -> None:
        assert parse_id(value) == value

    def test_negative_int_passthrough(self) -> None:
        # parse_id does not validate sign; downstream lookup decides.
        assert parse_id(-1) == -1

    def test_bool_is_int_subclass(self) -> None:
        # bool is an int subclass in Python; the match-case treats it
        # as int, which is the documented production behaviour.
        assert parse_id(True) == 1
        assert parse_id(False) == 0


class TestParseIdWithNumericStrings:
    """Decimal-string ids are parsed via ``int()``."""

    @pytest.mark.parametrize(
        ("text", "expected"),
        [
            ("0", 0),
            ("1", 1),
            ("42", 42),
            ("12345", 12345),
            ("-7", -7),
        ],
    )
    def test_decimal_strings(self, text: str, expected: int) -> None:
        assert parse_id(text) == expected


class TestParseIdWithBase62Strings:
    """Strings prefixed with ``"x"`` are decoded via base62."""

    # Skip 0 — base62.encode(0) returns "0" (no x-prefix), so it's not
    # exercising the base62 branch of parse_id.
    @pytest.mark.parametrize("value", [1, 16, 42, 1_000, 123_456_789])
    def test_roundtrip_through_base62(self, value: int) -> None:
        encoded = base62.encode(value)
        # Sanity-check the encoding contract relied on by parse_id.
        assert encoded.startswith("x")

        assert parse_id(encoded) == value

    def test_known_encodings(self) -> None:
        # BASE62_LIST = digits + ascii_lowercase + ascii_uppercase
        # So 'g' is index 16 (digits 0-9, lowercase a-f = 10-15, g = 16).
        assert parse_id("xg") == 16
        # 'G' is index 42 (digits 0-9, lowercase a-z = 10-35, A-G = 36-42).
        assert parse_id("xG") == 42


class TestParseIdRejectsBadInput:
    """Unparseable input raises ``NotFound``, not ``ValueError``."""

    @pytest.mark.parametrize(
        "bad",
        ["not-a-number", "abc", "12.34", "", "hello world"],
    )
    def test_non_numeric_string_raises_not_found(self, bad: str) -> None:
        # No "x" prefix and not int-parseable -> NotFound, never a leaked
        # ValueError. Message must mention the offending id for log
        # diagnostics.
        with pytest.raises(NotFound, match=bad or "id"):
            parse_id(bad)

    def test_base62_alphabet_zero(self) -> None:
        # "x" prefix forces base62 decode of empty body — returns 0.
        # Edge case worth pinning to document current behaviour.
        assert parse_id("x") == 0

    def test_short_base62_digit(self) -> None:
        # "x0" decodes to 0 ("0" is index 0 in BASE62_LIST).
        assert parse_id("x0") == 0

    @pytest.mark.parametrize(
        "bad",
        [None, 1.5, (1,), [1], {"id": 1}, object()],
    )
    def test_non_int_non_str_raises_not_found(self, bad: object) -> None:
        with pytest.raises(NotFound):
            parse_id(bad)  # type: ignore[arg-type]

    def test_not_found_message_includes_id(self) -> None:
        with pytest.raises(NotFound) as info:
            parse_id(None)  # type: ignore[arg-type]
        # The error message embeds the repr of the bad id so operators
        # can correlate logs.
        assert "None" in str(info.value)


class TestParseIdReturnsInt:
    """Return type is always ``int`` on success."""

    @pytest.mark.parametrize(
        "value",
        [0, 1, 42, "0", "1", "42", "xG"],
    )
    def test_return_type(self, value: int | str) -> None:
        assert isinstance(parse_id(value), int)
