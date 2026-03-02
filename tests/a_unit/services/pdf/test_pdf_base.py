# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Unit tests for services/pdf/base.py."""

from __future__ import annotations

import pytest

from app.services.pdf.base import to_pdf


class TestToPdf:
    """Test to_pdf singledispatch function."""

    def test_raises_for_unknown_type(self):
        """to_pdf should raise NotImplementedError for unknown types."""
        with pytest.raises(NotImplementedError, match="Cannot transform"):
            to_pdf("unknown object")

    def test_raises_for_dict(self):
        """to_pdf should raise NotImplementedError for dict."""
        with pytest.raises(NotImplementedError, match="Cannot transform"):
            to_pdf({"key": "value"})

    def test_raises_for_list(self):
        """to_pdf should raise NotImplementedError for list."""
        with pytest.raises(NotImplementedError, match="Cannot transform"):
            to_pdf([1, 2, 3])

    def test_raises_for_none(self):
        """to_pdf should raise NotImplementedError for None."""
        with pytest.raises(NotImplementedError, match="Cannot transform"):
            to_pdf(None)
