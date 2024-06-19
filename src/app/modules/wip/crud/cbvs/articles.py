# Copyright (c) 2021-2024 - Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from typing import cast

from flask import Flask, flash, g, redirect, render_template, request, send_file
from flask_classful import route
from flask_super.registry import register
from sqlalchemy_utils.types.arrow import arrow
from svcs.flask import container
from werkzeug.exceptions import NotFound

from app.flask.extensions import db
from app.flask.routing import url_for
from app.models.repositories import ArticleRepository
from app.modules.wip.models.newsroom import Article
from app.modules.wip.models.newsroom.article import ArticleStatus, Image
from app.services.blobs import BlobService
from app.settings.constants import MAX_IMAGE_SIZE
from app.signals import article_published, article_unpublished

from ._base import BaseWipView
from ._forms import ArticleForm
from ._table import BaseTable, get_name


class ArticlesTable(BaseTable):
    id = "articles-table"

    columns = [
        {
            "name": "titre",
            "label": "Titre",
            "class": "max-w-0 w-full truncate",
        },
        {
            "name": "media",
            "label": "Média",
            "class": "max-w-48 truncate",
            "render": get_name,
        },
        {
            "name": "status",
            "label": "Statut",
        },
        {
            "name": "created_at",
            "label": "Création",
            "class": "max-w-48 truncate",
        },
        {
            "name": "$actions",
            "label": "",
        },
    ]

    def __init__(self, q=""):
        super().__init__(Article, q)

    def url_for(self, obj, _action="get", **kwargs):
        return url_for(f"ArticlesWipView:{_action}", id=obj.id, **kwargs)

    def get_actions(self, item):
        actions = [
            {
                "label": "Voir",
                "url": self.url_for(item),
            },
            {
                "label": "Modifier",
                "url": self.url_for(item, "edit"),
            },
            {
                "label": "Images",
                "url": self.url_for(item, "images"),
            },
        ]
        if item.status == ArticleStatus.DRAFT:
            actions.append(
                {
                    "label": "Publier",
                    "url": self.url_for(item, "publish"),
                }
            )
        else:
            actions.append(
                {
                    "label": "Dépublier",
                    "url": self.url_for(item, "unpublish"),
                }
            )
        actions += [
            {
                "label": "Supprimer",
                "url": self.url_for(item, "delete"),
            },
        ]
        return actions


class ArticlesWipView(BaseWipView):
    name = "articles"

    model_class = Article
    repo_class = ArticleRepository
    table_class = ArticlesTable
    form_class = ArticleForm
    doc_type = "article"

    route_base = "articles"
    path = "/wip/articles/"

    # UI
    icon = "newspaper"

    label_main = "Newsroom: articles"
    label_list = "Liste des articles"
    label_new = "Créer un article"
    label_view = "Voir l'article"
    label_edit = "Modifier l'article"

    table_id = "articles-table-body"

    msg_delete_ok = "L'article a été supprimé"
    msg_delete_ko = "Vous n'êtes pas autorisé à supprimer cet article"

    def _post_update_model(self, model: Article):
        if not model.published_at:
            model.published_at = arrow.now("Europe/Paris")
            model.status = ArticleStatus.PUBLIC
            if g.user.organisation_id:
                model.publisher_id = g.user.organisation_id

    def publish(self, id: int):
        repo = self._get_repo()
        article = cast(Article, self._get_model(id))
        article.status = ArticleStatus.PUBLIC
        repo.update(article, auto_commit=True)
        flash("L'article a été publié")
        article_published.send(article)
        return redirect(self._url_for("index"))

    def unpublish(self, id: int):
        repo = self._get_repo()
        article = cast(Article, self._get_model(id))
        article.status = ArticleStatus.DRAFT
        repo.update(article, auto_commit=True)
        flash("L'article a été dépublié")
        article_unpublished.send(article)
        return redirect(self._url_for("index"))

    @route("/<int:id>/images/", methods=["GET", "POST"])
    def images(self, id: int):
        article = cast(Article, self._get_model(id))

        action = request.form.get("_action")
        if action == "cancel":
            return redirect(self._url_for("index"))

        if action == "add-image":
            return self._add_image(article)

        title = f"Images pour l'article - {article.title}"
        self.update_breadcrumbs(label=article.title)

        ctx = {
            "title": title,
            "article": article,
        }

        html = render_template("wip/article/images.j2", **ctx)
        return html

    def _add_image(self, article: Article):
        article_repo = self._get_repo()
        blob_service = container.get(BlobService)

        image = request.files.get("image")
        caption = request.form.get("caption", "").strip()
        copyright = request.form.get("copyright", "").strip()

        image_bytes = image.read()
        if not image_bytes:
            flash("L'image est vide")
            return redirect("")
        if len(image_bytes) >= MAX_IMAGE_SIZE:
            flash("L'image est trop volumineuse")
            return redirect("")

        blob = blob_service.save(image_bytes)

        image = Image(
            caption=caption,
            copyright=copyright,
            blob_id=blob.id,
            owner=article.owner,
        )
        article.add_image(image)
        article_repo.update(article, auto_commit=True)
        return redirect("")

    @route("/<int:article_id>/images/<int:image_id>")
    def image(self, article_id: int, image_id: int):
        article = cast(Article, self._get_model(article_id))
        for image in article.images:
            if image.id == image_id:
                break
        else:
            raise NotFound

        blob_service = container.get(BlobService)
        blob_path = blob_service.get_path(image.blob_id)
        return send_file(blob_path)

    @route("/<int:article_id>/images/<int:image_id>/delete", methods=["POST"])
    def delete_image(self, article_id: int, image_id: int):
        article = cast(Article, self._get_model(article_id))
        image = article.get_image(image_id)
        if not image:
            raise NotFound

        article.delete_image(image)
        db.session.delete(image)
        db.session.commit()

        return redirect(url_for("ArticlesWipView:images", id=article_id))

    @route("/<int:article_id>/images/<int:image_id>/move", methods=["POST"])
    def move_image(self, article_id: int, image_id: int):
        article = cast(Article, self._get_model(article_id))
        image = article.get_image(image_id)
        if not image:
            raise NotFound

        direction = request.form.get("direction")

        images = article.sorted_images
        assert [im.position for im in images] == list(range(len(images)))

        if direction == "up":
            prev_image = images[image.position - 1]
            image.position -= 1
            prev_image.position += 1
        elif direction == "down":
            next_image = images[image.position + 1]
            image.position += 1
            next_image.position -= 1

        db.session.commit()

        return redirect(url_for("ArticlesWipView:images", id=article_id))


@register
def register_on_app(app: Flask):
    ArticlesWipView.register(app)
