# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Repositories for wire module models."""

from __future__ import annotations

from flask_super.decorators import service

from app.services.repositories import Repository

from .models import ArticlePost, PressReleasePost


@service
class ArticlePostRepository(Repository[ArticlePost]):
    """Repository for ArticlePost model."""

    model_type = ArticlePost

    def get_by_newsroom_id(self, newsroom_id: int) -> ArticlePost | None:
        """Get an ArticlePost by its corresponding newsroom article ID."""
        return self.get_one_or_none(ArticlePost.newsroom_id == newsroom_id)


@service
class PressReleasePostRepository(Repository[PressReleasePost]):
    """Repository for PressReleasePost model."""

    model_type = PressReleasePost

    def get_by_newsroom_id(self, newsroom_id: int) -> PressReleasePost | None:
        """Get a PressReleasePost by its corresponding newsroom communique ID."""
        return self.get_one_or_none(PressReleasePost.newsroom_id == newsroom_id)
