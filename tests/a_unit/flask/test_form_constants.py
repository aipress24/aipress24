# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Unit tests for flask/forms/_constants.py"""

from __future__ import annotations

import pytest

from app.flask.forms._constants import get_choices


@pytest.mark.parametrize(
    "key",
    ["genre", "genre-com", "events", "sector", "topic", "section", "language", "copyright-mention"],
)
def test_get_choices_returns_collection_for_valid_key(key: str) -> None:
    """Test get_choices returns collection for valid keys."""
    result = get_choices(key)
    assert isinstance(result, (list, tuple, dict))


def test_get_choices_raises_for_invalid_key() -> None:
    """Test get_choices raises ValueError for invalid keys."""
    with pytest.raises(ValueError, match="Invalid key"):
        get_choices("invalid-key")

    with pytest.raises(ValueError, match="Invalid key"):
        get_choices("")
