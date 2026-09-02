# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Repositories for wire module models."""

from __future__ import annotations

from flask_super.decorators import service

from app.services.repositories import PublishableRepository

from .models import ArticlePost, PressReleasePost


@service
class ArticlePostRepository(PublishableRepository[ArticlePost]):
    """Repository for ArticlePost model."""

    model_type = ArticlePost


@service
class PressReleasePostRepository(PublishableRepository[PressReleasePost]):
    """Repository for PressReleasePost model."""

    model_type = PressReleasePost
