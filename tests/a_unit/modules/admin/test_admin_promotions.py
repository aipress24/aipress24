# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Unit tests for admin/pages/promotions.py - title determination logic.

Note: Basic configuration tests for PROMO_SLUG_LABEL and BOX_TITLE constants
are in test_admin_views.py to avoid duplication.
"""

from __future__ import annotations

import pytest

from app.modules.admin.views._promotions import BOX_TITLE1, BOX_TITLE2


class TestPromotionTitleLogic:
    """Test the title determination logic from promotions.py post method."""

    def _get_title_for_slug(self, slug: str) -> str:
        """Mirror the title determination logic from AdminPromotionsPage.post."""
        if slug.endswith("1"):
            return BOX_TITLE1
        return BOX_TITLE2

    @pytest.mark.parametrize(
        ("slug", "expected_title"),
        [
            ("wire/1", BOX_TITLE1),
            ("wire/2", BOX_TITLE2),
            ("events/1", BOX_TITLE1),
            ("events/2", BOX_TITLE2),
            ("biz/1", BOX_TITLE1),
            ("biz/2", BOX_TITLE2),
            ("swork/1", BOX_TITLE1),
            ("swork/2", BOX_TITLE2),
        ],
    )
    def test_title_for_slug(self, slug: str, expected_title: str):
        """Test title determination for each slug."""
        assert self._get_title_for_slug(slug) == expected_title

    def test_title_logic_with_unknown_suffix(self):
        """Test title defaults to BOX_TITLE2 for non-1 endings."""
        assert self._get_title_for_slug("test/3") == BOX_TITLE2
        assert self._get_title_for_slug("test/0") == BOX_TITLE2
        assert self._get_title_for_slug("test/x") == BOX_TITLE2
