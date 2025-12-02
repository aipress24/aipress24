# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Tests for promotion service."""

from __future__ import annotations

from flask_sqlalchemy import SQLAlchemy
from svcs.flask import container

from app.models.admin import Promotion
from app.services.promotions import PromotionService
from app.services.promotions._models import PromotionRepository


class TestPromotionService:
    """Test suite for PromotionService class."""

    def test_store_promotion_creates_new(self, db: SQLAlchemy) -> None:
        """Should create new promotion when slug doesn't exist."""
        service = PromotionService()

        promo = service.store_promotion(
            slug="test-promo",
            title="Test Title",
            body="Test Body",
        )

        assert promo is not None
        assert promo.slug == "test-promo"
        assert promo.title == "Test Title"
        assert promo.body == "Test Body"

    def test_store_promotion_updates_existing(self, db: SQLAlchemy) -> None:
        """Should update existing promotion when slug exists."""
        service = PromotionService()

        # Create initial promotion
        service.store_promotion(
            slug="test-promo",
            title="Original Title",
            body="Original Body",
        )

        # Update it
        updated = service.store_promotion(
            slug="test-promo",
            title="Updated Title",
            body="Updated Body",
        )

        assert updated.title == "Updated Title"
        assert updated.body == "Updated Body"

    def test_get_promotion_returns_existing(self, db: SQLAlchemy) -> None:
        """Should return promotion when it exists."""
        service = PromotionService()

        # Create a promotion first
        service.store_promotion(
            slug="test-promo",
            title="Test Title",
            body="Test Body",
        )

        # Get it
        promo = service.get_promotion("test-promo")

        assert promo is not None
        assert promo.slug == "test-promo"
        assert promo.title == "Test Title"

    def test_get_promotion_returns_none_for_nonexistent(self, db: SQLAlchemy) -> None:
        """Should return None when promotion doesn't exist."""
        service = PromotionService()

        promo = service.get_promotion("nonexistent-slug")

        assert promo is None


class TestPromotionRepository:
    """Test suite for PromotionRepository class."""

    def test_get_one_or_none_returns_none_when_not_found(self, db: SQLAlchemy) -> None:
        """Should return None when promotion not found."""
        repo = container.get(PromotionRepository)

        result = repo.get_one_or_none(slug="nonexistent")

        assert result is None

    def test_get_one_or_none_returns_promotion(self, db: SQLAlchemy) -> None:
        """Should return promotion when found."""
        repo = container.get(PromotionRepository)

        # Create a promotion directly
        promo = Promotion(slug="test-slug", title="Test", body="Body")
        db.session.add(promo)
        db.session.flush()

        result = repo.get_one_or_none(slug="test-slug")

        assert result is not None
        assert result.slug == "test-slug"

    def test_add_creates_promotion(self, db: SQLAlchemy) -> None:
        """Should create promotion via repository."""
        repo = container.get(PromotionRepository)

        promo = Promotion(slug="new-promo", title="New", body="Body")
        result = repo.add(promo)
        repo.session.flush()

        assert result.slug == "new-promo"

        # Verify it was persisted
        found = repo.get_one_or_none(slug="new-promo")
        assert found is not None
