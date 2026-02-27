# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""E2E tests for admin promotions views."""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.modules.admin.views.promotions import (
    BOX_TITLE1,
    BOX_TITLE2,
    PROMO_SLUG_LABEL,
)

if TYPE_CHECKING:
    from flask.testing import FlaskClient

    from app.models.auth import User


class TestPromotionsPage:
    """Tests for the promotions management page."""

    def test_promotions_page_accessible(
        self,
        admin_client: FlaskClient,
        admin_user: User,
    ):
        """Test that promotions page is accessible."""
        response = admin_client.get("/admin/promotions")
        assert response.status_code in (200, 302)

    def test_promotions_page_shows_options(
        self,
        admin_client: FlaskClient,
        admin_user: User,
    ):
        """Test that promotions page shows promo options."""
        response = admin_client.get("/admin/promotions")
        if response.status_code == 200:
            html = response.data.decode()
            # Should show at least one of the promo options
            assert "wire" in html.lower() or "promo" in html.lower()


class TestPromotionsPost:
    """Tests for saving promotions."""

    def test_save_promotion_redirects(
        self,
        admin_client: FlaskClient,
        admin_user: User,
    ):
        """Test saving a promotion redirects."""
        response = admin_client.post(
            "/admin/promotions",
            data={
                "promo": "wire/1",
                "content": "New promo content",
            },
            follow_redirects=False,
        )

        assert response.status_code == 302

    def test_save_promotion_empty_slug(
        self,
        admin_client: FlaskClient,
        admin_user: User,
    ):
        """Test saving with empty slug still redirects."""
        response = admin_client.post(
            "/admin/promotions",
            data={
                "promo": "",
                "content": "Some content",
            },
            follow_redirects=False,
        )

        assert response.status_code == 302


class TestPromoConstants:
    """Tests for promotion constants."""

    def test_promo_slug_label_structure(self):
        """Test that PROMO_SLUG_LABEL has correct structure."""
        assert len(PROMO_SLUG_LABEL) == 8
        for item in PROMO_SLUG_LABEL:
            assert "value" in item
            assert "label" in item

    def test_promo_slug_label_values(self):
        """Test that PROMO_SLUG_LABEL has expected values."""
        values = [item["value"] for item in PROMO_SLUG_LABEL]
        assert "wire/1" in values
        assert "wire/2" in values
        assert "events/1" in values
        assert "events/2" in values
        assert "biz/1" in values
        assert "biz/2" in values
        assert "swork/1" in values
        assert "swork/2" in values

    def test_box_titles(self):
        """Test box title constants."""
        assert BOX_TITLE1 == "AiPRESS24 vous informe"
        assert BOX_TITLE2 == "AiPRESS24 vous suggère"
