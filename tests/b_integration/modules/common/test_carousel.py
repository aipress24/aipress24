# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Unit tests for common/components/carousel.py."""

from __future__ import annotations

import pytest

from app.models.auth import User
from app.modules.common.components.carousel import Carousel
from app.modules.wire.models import ArticlePost


class TestCarouselTypeValidation:
    """Test Carousel type checking behavior."""

    def test_rejects_raw_article_post(self, app, db_session):
        """Carousel should reject ArticlePost - it requires ArticleVM wrapper."""
        with app.test_request_context():
            user = User(email="test@example.com")
            db_session.add(user)
            db_session.flush()

            article = ArticlePost(owner=user, title="Test")
            db_session.add(article)
            db_session.flush()

            carousel = Carousel(post=article)

            with pytest.raises(
                TypeError, match="expected ArticleVM, PressReleaseVM, or CommuniqueVM"
            ):
                carousel.get_slides()
