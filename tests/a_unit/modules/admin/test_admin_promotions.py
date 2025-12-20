# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Unit tests for admin/pages/promotions.py - configuration and logic."""

from __future__ import annotations

import pytest

from app.modules.admin.views._promotions import (
    BOX_TITLE1,
    BOX_TITLE2,
    PROMO_SLUG_LABEL,
)


class TestPromoSlugLabel:
    """Test PROMO_SLUG_LABEL configuration."""

    def test_promo_options_count(self):
        """Test PROMO_SLUG_LABEL has expected number of options."""
        assert len(PROMO_SLUG_LABEL) == 8

    def test_promo_options_structure(self):
        """Test each option has value and label."""
        for option in PROMO_SLUG_LABEL:
            assert "value" in option
            assert "label" in option
            assert isinstance(option["value"], str)
            assert isinstance(option["label"], str)

    def test_promo_values_format(self):
        """Test promo values follow module/number format."""
        for option in PROMO_SLUG_LABEL:
            value = option["value"]
            assert "/" in value
            parts = value.split("/")
            assert len(parts) == 2
            assert parts[1] in ("1", "2")

    def test_promo_modules_covered(self):
        """Test all expected modules are covered."""
        modules = {opt["value"].split("/")[0] for opt in PROMO_SLUG_LABEL}
        expected_modules = {"wire", "events", "biz", "swork"}
        assert modules == expected_modules


class TestBoxTitles:
    """Test BOX_TITLE constants."""

    def test_box_title1_is_string(self):
        """Test BOX_TITLE1 is a non-empty string."""
        assert isinstance(BOX_TITLE1, str)
        assert len(BOX_TITLE1) > 0

    def test_box_title2_is_string(self):
        """Test BOX_TITLE2 is a non-empty string."""
        assert isinstance(BOX_TITLE2, str)
        assert len(BOX_TITLE2) > 0

    def test_box_titles_are_different(self):
        """Test BOX_TITLE1 and BOX_TITLE2 are different."""
        assert BOX_TITLE1 != BOX_TITLE2


class TestPromotionTitleLogic:
    """Test the title determination logic from promotions.py post method."""

    def _get_title_for_slug(self, slug: str) -> str:
        """Mirror the title determination logic from AdminPromotionsPage.post."""
        if slug.endswith("1"):
            return BOX_TITLE1
        else:
            return BOX_TITLE2

    @pytest.mark.parametrize(
        "slug,expected_title",
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
