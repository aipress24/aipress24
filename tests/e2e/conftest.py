# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Splinter tests configuration.

These tests use the shared app fixture from tests/conftest.py.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from splinter import Browser

if TYPE_CHECKING:
    from flask import Flask


@pytest.fixture(scope="module")
def browser(app: Flask) -> Browser:
    """Provide a splinter browser instance for a test module."""
    return Browser("flask", app=app)
