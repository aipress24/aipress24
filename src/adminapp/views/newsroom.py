"""Newsroom admin views for articles, subjects, and commands."""

# Copyright (c) 2024, Abilian SAS & TCA
from __future__ import annotations

from typing import ClassVar

from sqladmin import Admin, ModelView, action
from starlette.requests import Request
from starlette.responses import RedirectResponse

from app.modules.wip.models import (
    Article,
    AvisEnquete,
    Commande,
    Sujet,
)


class ArticleAdmin(ModelView, model=Article):
    """Admin interface for Article model."""

    icon = "fa-solid fa-newspaper"
    category = "Newsroom"

    column_list: ClassVar = [Article.id, Article.published_at, Article.titre]
    column_searchable_list: ClassVar = [Article.titre, Article.contenu]
    column_sortable_list: ClassVar = [Article.published_at]

    # NB: not working, just an example
    @action(
        name="approve_article",
        label="Approve",
        confirmation_message="Are you sure?",
        add_in_detail=True,
        add_in_list=True,
    )
    async def approve_articles(self, request: Request):
        """Approve selected articles.

        Args:
            request: The HTTP request containing article IDs to approve.

        Returns:
            RedirectResponse: Redirect back to the admin interface.
        """
        pks = request.query_params.get("pks", "").split(",")
        if pks:
            for pk in pks:
                # NB: there is a bug here - get_object_for_edit expects Request, not pk
                _model: Article = await self.get_object_for_edit(pk)  # type: ignore[arg-type]
                # ...

        referer = request.headers.get("Referer")
        if referer:
            return RedirectResponse(referer)
        return RedirectResponse(request.url_for("admin:list", identity=self.identity))


class SujetAdmin(ModelView, model=Sujet):
    """Admin interface for Sujet model."""

    icon = "fa-solid fa-pen-nib"
    category = "Newsroom"

    column_list: ClassVar = [Sujet.id, Sujet.created_at, Sujet.titre]
    column_searchable_list: ClassVar = [Sujet.titre, Sujet.contenu]
    column_sortable_list: ClassVar = [Sujet.created_at]


class CommandeAdmin(ModelView, model=Commande):
    """Admin interface for Commande model."""

    icon = "fa-solid fa-check"
    category = "Newsroom"

    column_list: ClassVar = [Commande.id, Commande.created_at, Commande.titre]
    column_searchable_list: ClassVar = [Commande.titre, Commande.contenu]
    column_sortable_list: ClassVar = [Commande.created_at]


class AvisEnqueteAdmin(ModelView, model=AvisEnquete):
    """Admin interface for AvisEnquete model."""

    icon = "fa-solid fa-bullhorn"
    category = "Newsroom"

    column_list: ClassVar = [AvisEnquete.id, AvisEnquete.created_at, AvisEnquete.titre]
    column_searchable_list: ClassVar = [AvisEnquete.titre, AvisEnquete.contenu]
    column_sortable_list: ClassVar = [AvisEnquete.created_at]


def register(admin: Admin) -> None:
    """Register newsroom-related admin views.

    Args:
        admin: Admin instance to register views to.
    """
    admin.add_view(SujetAdmin)
    admin.add_view(CommandeAdmin)
    admin.add_view(ArticleAdmin)
    admin.add_view(AvisEnqueteAdmin)
