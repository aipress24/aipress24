"""Wire admin views for article posts."""

# Copyright (c) 2024, Abilian SAS & TCA
from __future__ import annotations

from typing import ClassVar

from sqladmin import Admin, ModelView

from app.modules.wire.models import ArticlePost


class PostAdmin(ModelView, model=ArticlePost):
    """Admin interface for ArticlePost model."""

    icon = "fa-solid fa-newspaper"
    category = "Wire"

    column_list: ClassVar = [ArticlePost.id, ArticlePost.created_at, ArticlePost.title]
    column_searchable_list: ClassVar = [ArticlePost.title, ArticlePost.content]
    column_sortable_list: ClassVar = [ArticlePost.created_at]


def register(admin: Admin) -> None:
    """Register wire-related admin views.

    Args:
        admin: Admin instance to register views to.
    """
    admin.add_view(PostAdmin)
