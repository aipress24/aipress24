# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Unit tests for flask/lib/toaster.py"""

from __future__ import annotations

import json

from flask import Response

from app.flask.lib.toaster import toast


def test_toast_sets_hx_trigger_with_message() -> None:
    """Test toast sets HX-Trigger header with showToast event."""
    response = Response()

    toast(response, "Operation completed")

    trigger = json.loads(response.headers["HX-Trigger"])
    assert trigger["showToast"] == "Operation completed"


def test_toast_handles_special_characters() -> None:
    """Test toast handles unicode and special characters."""
    response = Response()

    toast(response, "Succès! ✓ with 'quotes'")

    trigger = json.loads(response.headers["HX-Trigger"])
    assert trigger["showToast"] == "Succès! ✓ with 'quotes'"
