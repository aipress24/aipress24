# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Unit tests for wip/pages/utils.py"""

from __future__ import annotations

import io
import sys
from contextlib import contextmanager

from app.modules.wip.pages.utils import info, warning


@contextmanager
def capture_stderr():
    """Context manager to capture stderr output."""
    captured = io.StringIO()
    sys.stderr, old = captured, sys.stderr
    try:
        yield captured
    finally:
        sys.stderr = old


def test_info_prints_to_stderr() -> None:
    """Test info prints arguments to stderr."""
    with capture_stderr() as captured:
        info("hello", "world", 123)

    assert "hello world 123" in captured.getvalue()


def test_warning_prints_with_prefix() -> None:
    """Test warning prints with 'Warning:' prefix."""
    with capture_stderr() as captured:
        warning("something", "happened")

    assert "Warning: something happened" in captured.getvalue()
