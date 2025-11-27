# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Unit tests for flask/lib/breadcrumbs.py"""

from __future__ import annotations

import pytest

from app.flask.lib.breadcrumbs import BreadCrumb


def test_breadcrumb_stores_label_and_url() -> None:
    """Test BreadCrumb stores label/url and provides aliases."""
    crumb = BreadCrumb(label="Home", url="/home")

    assert crumb.label == "Home"
    assert crumb.url == "/home"
    # Aliases
    assert crumb.name == "Home"
    assert crumb.href == "/home"


def test_breadcrumb_is_frozen() -> None:
    """Test BreadCrumb is immutable."""
    crumb = BreadCrumb(label="Test", url="/test")

    with pytest.raises(Exception):  # FrozenInstanceError
        crumb.label = "Changed"  # type: ignore


def test_breadcrumb_equality() -> None:
    """Test BreadCrumb equality based on attrs."""
    crumb1 = BreadCrumb(label="Home", url="/")
    crumb2 = BreadCrumb(label="Home", url="/")
    crumb3 = BreadCrumb(label="Home", url="/different")

    assert crumb1 == crumb2
    assert crumb1 != crumb3
