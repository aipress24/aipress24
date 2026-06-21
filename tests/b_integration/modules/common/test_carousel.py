# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Unit tests for common/components/carousel.py."""

from __future__ import annotations

import pytest

from app.models.auth import User
from app.modules.common.components.carousel import Carousel
from app.modules.common.components.post_card import ArticleVM
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


class TestCarouselSlidesMemoized:
    """`Component._get_context()` reads get_slides / slides / alpine_data
    separately — each used to reload the newsroom item + its images
    (3× crm_communique + 3× crm_image on a press-release page). They must
    all share one computed result."""

    def test_slides_computed_once_per_render(self, app, db_session):
        with app.test_request_context():
            user = User(email="memo@example.com")
            db_session.add(user)
            db_session.flush()
            article = ArticlePost(owner=user, title="Memo")
            db_session.add(article)
            db_session.flush()

            carousel = Carousel(post=ArticleVM(article))

            slides = carousel.get_slides()
            # Same object returned every time + via both property accessors
            # → the (DB-loading) compute happens exactly once.
            assert carousel.get_slides() is slides
            assert carousel.slides is slides
            assert carousel.alpine_data["slides"] is slides
