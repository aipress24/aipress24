# Copyright (c) 2024, Abilian SAS & TCA
from __future__ import annotations

from sqladmin import Admin, ModelView, action
from starlette.requests import Request
from starlette.responses import RedirectResponse

from app.modules.wip.models import (
    Article,
    AvisEnquete,
    Commande,
    JustifPublication,
    Sujet,
)


class ArticleAdmin(ModelView, model=Article):
    icon = "fa-solid fa-newspaper"
    category = "Newsroom"

    column_list = [Article.id, Article.published_at, Article.titre]
    column_searchable_list = [Article.titre, Article.contenu]
    column_sortable_list = [Article.published_at]

    # NB: not working, just an example
    @action(
        name="approve_article",
        label="Approve",
        confirmation_message="Are you sure?",
        add_in_detail=True,
        add_in_list=True,
    )
    async def approve_articles(self, request: Request):
        pks = request.query_params.get("pks", "").split(",")
        if pks:
            for pk in pks:
                # NB: there is a bug here
                _model: Article = await self.get_object_for_edit(pk)
                # ...

        referer = request.headers.get("Referer")
        if referer:
            return RedirectResponse(referer)
        return RedirectResponse(request.url_for("admin:list", identity=self.identity))


class SujetAdmin(ModelView, model=Sujet):
    icon = "fa-solid fa-pen-nib"
    category = "Newsroom"

    column_list = [Sujet.id, Sujet.created_at, Sujet.titre]
    column_searchable_list = [Sujet.titre, Sujet.contenu]
    column_sortable_list = [Sujet.created_at]


class CommandeAdmin(ModelView, model=Commande):
    icon = "fa-solid fa-check"
    category = "Newsroom"

    column_list = [Commande.id, Commande.created_at, Commande.titre]
    column_searchable_list = [Commande.titre, Commande.contenu]
    column_sortable_list = [Commande.created_at]


class AvisEnqueteAdmin(ModelView, model=AvisEnquete):
    icon = "fa-solid fa-bullhorn"
    category = "Newsroom"

    column_list = [AvisEnquete.id, AvisEnquete.created_at, AvisEnquete.titre]
    column_searchable_list = [AvisEnquete.titre, AvisEnquete.contenu]
    column_sortable_list = [AvisEnquete.created_at]


class JustifPublicationAdmin(ModelView, model=JustifPublication):
    icon = "fa-solid fa-medal"
    category = "Newsroom"

    column_list = [
        JustifPublication.id,
        JustifPublication.created_at,
        JustifPublication.titre,
    ]
    column_searchable_list = [JustifPublication.titre, JustifPublication.contenu]
    column_sortable_list = [JustifPublication.created_at]


def register(admin: Admin) -> None:
    admin.add_view(SujetAdmin)
    admin.add_view(CommandeAdmin)
    admin.add_view(ArticleAdmin)
    admin.add_view(AvisEnqueteAdmin)
    admin.add_view(JustifPublicationAdmin)
