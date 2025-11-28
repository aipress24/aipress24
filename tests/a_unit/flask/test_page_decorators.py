# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Unit tests for flask/lib/pages/_decorators.py"""

from __future__ import annotations

from app.flask.lib.pages._decorators import expose


def test_expose_sets_metadata() -> None:
    """Test expose decorator sets _pagic_metadata on method."""

    @expose
    def my_method():
        pass

    assert hasattr(my_method, "_pagic_metadata")
    assert my_method._pagic_metadata["exposed"] is True


def test_expose_preserves_existing_metadata() -> None:
    """Test expose decorator preserves existing metadata."""

    def my_method():
        pass

    my_method._pagic_metadata = {"custom": "value"}

    decorated = expose(my_method)

    assert decorated._pagic_metadata["custom"] == "value"
    assert decorated._pagic_metadata["exposed"] is True


def test_expose_returns_same_function() -> None:
    """Test expose decorator returns the same function."""

    def my_method():
        return "result"

    decorated = expose(my_method)

    assert decorated() == "result"
    assert decorated is my_method
