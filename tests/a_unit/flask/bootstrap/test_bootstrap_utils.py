# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Unit tests for flask/bootstrap/utils.py"""

from __future__ import annotations

import io
import sys

from app.flask.bootstrap.utils import g, show_memory_usage


def test_show_memory_usage_outputs_rss_info() -> None:
    """Test show_memory_usage prints RSS and Max RSS information."""
    g["max_rss"] = 0
    captured = io.StringIO()
    sys.stdout, old_stdout = captured, sys.stdout

    try:
        show_memory_usage()
    finally:
        sys.stdout = old_stdout

    output = captured.getvalue()
    assert "RSS:" in output
    assert "Max RSS:" in output
    assert "MB" in output
    assert g["max_rss"] > 0
