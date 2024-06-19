# Copyright (c) 2021-2024 - Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from app.lib.fts import tokenize


def test_tokenize() -> None:
    assert tokenize("Hello world") == ["hello", "world"]
    assert tokenize("Hello world!") == ["hello", "world"]
    assert tokenize("Hello-world!") == ["hello", "world"]
    assert tokenize("Hello\nworld!") == ["hello", "world"]
    assert tokenize("Hello\n\n\nworld!") == ["hello", "world"]
    assert tokenize("<p>Hello\n\n\nworld!</p>") == ["hello", "world"]
    assert tokenize("<a href='#'>Hello\n\n\nworld!</a>") == ["hello", "world"]
