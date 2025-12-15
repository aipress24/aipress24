# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Tests for lib/fts module (full-text search utilities)."""

from __future__ import annotations

import pytest

from app.lib.fts import tokenize, unicode_to_ascii


class TestTokenize:
    """Test suite for tokenize function."""

    @pytest.mark.parametrize(
        "input_text,expected",
        [
            # Basic tokenization
            ("Hello world", ["hello", "world"]),
            ("UPPERCASE TEXT", ["uppercase", "text"]),
            # Punctuation handling
            ("Hello world!", ["hello", "world"]),
            ("Hello, world.", ["hello", "world"]),
            # Special characters as separators
            ("Hello-world", ["hello", "world"]),
            ("Hello_world", ["helloworld"]),  # underscore doesn't split
            # Whitespace handling
            ("Hello\nworld", ["hello", "world"]),
            ("Hello\n\n\nworld", ["hello", "world"]),
            ("Hello   world", ["hello", "world"]),
            # HTML stripping
            ("<p>Hello</p>", ["hello"]),
            ("<p>Hello world!</p>", ["hello", "world"]),
            ("<a href='#'>Hello world!</a>", ["hello", "world"]),
            ("<div><span>Nested</span> content</div>", ["nested", "content"]),
            # Combined cases
            ("<p>Hello\n\n\nworld!</p>", ["hello", "world"]),
        ],
    )
    def test_tokenize(self, input_text: str, expected: list[str]) -> None:
        """Test tokenize handles various input formats."""
        assert tokenize(input_text) == expected

    def test_tokenize_empty_string(self) -> None:
        """Test tokenize with empty string."""
        assert tokenize("") == []

    def test_tokenize_only_punctuation(self) -> None:
        """Test tokenize with only punctuation."""
        assert tokenize("!@#$%^&*()") == []


class TestUnicodeToAscii:
    """Test suite for unicode_to_ascii function."""

    @pytest.mark.parametrize(
        "input_text,expected",
        [
            # Accented characters
            ("café", "cafe"),
            ("naïve", "naive"),
            ("résumé", "resume"),
            ("Ångström", "Angstrom"),
            ("Ñoño", "Nono"),
            # Regular ASCII (unchanged)
            ("hello", "hello"),
            ("HELLO", "HELLO"),
            ("hello123", "hello123"),
            # Empty string
            ("", ""),
            # Mixed content
            ("Hôtel & Café", "Hotel & Cafe"),
        ],
    )
    def test_unicode_to_ascii(self, input_text: str, expected: str) -> None:
        """Test unicode_to_ascii converts accented characters."""
        assert unicode_to_ascii(input_text) == expected
