# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Unit tests for public/views/debug.py."""

from __future__ import annotations

import pytest
from werkzeug.exceptions import Forbidden

from app.modules.public.views.debug import check_unsecure


class TestCheckUnsecure:
    """Test check_unsecure function."""

    def test_raises_forbidden_when_not_unsecure(self, app):
        """Test raises Forbidden when UNSECURE config is False."""
        app.config["UNSECURE"] = False

        with (
            app.app_context(),
            pytest.raises(Forbidden, match="not an unsecure environment"),
        ):
            check_unsecure()

    def test_raises_forbidden_when_unsecure_not_set(self, app):
        """Test raises Forbidden when UNSECURE config is not set."""
        app.config.pop("UNSECURE", None)

        with (
            app.app_context(),
            pytest.raises(Forbidden, match="not an unsecure environment"),
        ):
            check_unsecure()

    def test_passes_when_unsecure_true(self, app):
        """Test passes when UNSECURE config is True."""
        app.config["UNSECURE"] = True

        with app.app_context():
            # Should not raise
            check_unsecure()
