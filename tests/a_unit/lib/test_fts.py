# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from app.lib.fts import tokenize, unicode_to_ascii


def test_tokenize() -> None:
    assert tokenize("Hello world") == ["hello", "world"]
    assert tokenize("Hello world!") == ["hello", "world"]
    assert tokenize("Hello-world!") == ["hello", "world"]
    assert tokenize("Hello\nworld!") == ["hello", "world"]
    assert tokenize("Hello\n\n\nworld!") == ["hello", "world"]
    assert tokenize("<p>Hello\n\n\nworld!</p>") == ["hello", "world"]
    assert tokenize("<a href='#'>Hello\n\n\nworld!</a>") == ["hello", "world"]


def test_unicode_to_ascii() -> None:
    """Test unicode_to_ascii function."""
    # Test with accented characters
    assert unicode_to_ascii("café") == "cafe"
    assert unicode_to_ascii("naïve") == "naive"
    assert unicode_to_ascii("résumé") == "resume"

    # Test with regular ASCII
    assert unicode_to_ascii("hello") == "hello"

    # Test with empty string
    assert unicode_to_ascii("") == ""
