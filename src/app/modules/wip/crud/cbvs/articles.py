# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from flask import (
    Flask,
    flash,
    g,
    redirect,
    render_template,
    request,
)
from flask_classful import route
from flask_super.registry import register
from markupsafe import Markup
from sqlalchemy_utils.types.arrow import arrow
from werkzeug.exceptions import NotFound

from app.flask.extensions import db
from app.flask.lib.templates import templated
from app.flask.routing import url_for
from app.lib.file_object_utils import create_file_object
from app.lib.image_utils import extract_image_from_request
from app.logging import warn
from app.models.lifecycle import PublicationStatus
from app.modules.wip.models import Article, ArticleRepository, Image, ImageRepository
from app.settings.constants import MAX_IMAGE_SIZE
from app.signals import article_published, article_unpublished, article_updated

from ._base import BaseWipView
from ._forms import ArticleForm
from ._table import BaseTable

# Custom list template for articles: adds a discreet reminder banner
# pointing to the cession-droits policy page, visible only for users
# whose active BW is of type `media`. The banner is shown at the top
# of the newsroom article index — which is the landing page right
# after publishing an article (the publish handler redirects here).
# ref: `local-notes/specs/cession-droits-mvp.md` §7.3.
# language=jinja2
_ARTICLES_LIST_TEMPLATE = """
{% extends "wip/layout/_base.j2" %}
{% block body_content %}
  {% if rights_reminder %}
    <div class="mb-4 p-3 bg-blue-50 border border-blue-200 rounded text-sm text-blue-900 flex items-center justify-between gap-3">
      <span>
        ℹ️ Vos <strong>modalités de cession de droits</strong>
        s'appliquent automatiquement à chaque article publié.
      </span>
      <a href="{{ url_for('bw_activation.rights_policy') }}"
         class="text-blue-700 font-medium underline whitespace-nowrap">
        Gérer les modalités →
      </a>
    </div>
  {% endif %}
  {{ table.render() }}
{% endblock %}
"""


def _user_has_media_bw() -> bool:
    """True if the current user's active BW is of type `media`."""
    from app.modules.bw.bw_activation.models.business_wall import BWStatus
    from app.modules.bw.bw_activation.user_utils import current_business_wall

    user = g.user
    if not user or user.is_anonymous:
        return False
    bw = current_business_wall(user)
    return (
        bw is not None and bw.bw_type == "media" and bw.status == BWStatus.ACTIVE.value
    )


if TYPE_CHECKING:
    from app.lib.image_utils import UploadedImageData


class ArticlesTable(BaseTable):
    id = "articles-table"

    def __init__(self, q="") -> None:
        # self.columns = self.get_columns()
        super().__init__(Article, q)

    def get_columns(self):
        return [
            {
                "name": "titre",
                "label": "Titre",
                "class": "max-w-0 w-full truncate",
                "render": self.get_title_with_link,
            },
            {
                "name": "media",
                "label": "Média",
                "class": "max-w-48 truncate",
                "render": self.get_media_name,
            },
            {
                "name": "status",
                "label": "Statut",
            },
            {
                "name": "date_publication_aip24",
                "label": "Publication",
                "class": "max-w-48 truncate",
            },
            {
                "name": "$actions",
                "label": "",
            },
        ]

    def get_title_with_link(self, obj: Article):
        return Markup(
            f'<a href="{url_for("ArticlesWipView:get", id=obj.id)}">{obj.title}</a>'
        )

    def url_for(self, obj, _action="get", **kwargs):  # type: ignore[override]
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
        if item.status == PublicationStatus.DRAFT:
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

    @templated(_ARTICLES_LIST_TEMPLATE)
    def index(self) -> dict:
        q = request.args.get("q", "")
        self.update_breadcrumbs()
        return {
            "title": self.label_main,
            "table": self._make_table(q),
            "rights_reminder": _user_has_media_bw(),
        }

    def _post_update_model(self, model: Article) -> None:
        if not model.status:
            model.status = PublicationStatus.DRAFT  # type: ignore[assignment]
            model.published_at = arrow.now("Europe/Paris")  # type: ignore[assignment,union-attr]
            if g.user.organisation_id:
                model.publisher_id = g.user.organisation_id
        article_updated.send(model)

    def publish(self, id):
        repo = self._get_repo()
        article = cast("Article", self._get_model(id))

        # Use business method to publish (includes validation)
        try:
            publisher_id = g.user.organisation_id or None
            article.publish(publisher_id=publisher_id)
        except ValueError as e:
            flash(str(e), "error")
            return redirect(self._url_for("edit", id=id))

        repo.update(article, auto_commit=False)
        article_published.send(article)
        db.session.commit()
        flash("L'article a été publié")
        return redirect(self._url_for("index"))

    def unpublish(self, id):
        repo = self._get_repo()
        article = cast("Article", self._get_model(id))

        # Use business method to unpublish (includes validation)
        try:
            article.unpublish()
        except ValueError as e:
            flash(str(e), "error")
            return redirect(self._url_for("get", id=id))

        repo.update(article, auto_commit=False)
        article_unpublished.send(article)
        db.session.commit()
        flash("L'article a été dépublié")
        return redirect(self._url_for("index"))

    @route("/<int:id>/images/", methods=["GET", "POST"])
    def images(self, id: int):
        article = cast("Article", self._get_model(id))

        action = request.form.get("_action")
        match action:
            case "cancel":
                return redirect(self._url_for("index"))
            case "add-image":
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
        image_repo = ImageRepository(session=db.session)  # type: ignore[arg-type]

        # Handle both regular file upload and base64 data URL from cropper
        result: UploadedImageData | None = extract_image_from_request(
            file_storage=request.files.get("image"),
            data_url=request.form.get("image"),
            orig_filename=request.form.get("image_filename") or None,
        )

        if result is None:
            flash("L'image est vide")
            return redirect(url_for("ArticlesWipView:images", id=article.id))

        image_bytes = result.bytes
        image_filename = result.filename
        image_content_type = result.content_type
        if len(image_bytes) >= MAX_IMAGE_SIZE:
            flash("L'image est trop volumineuse")
            return redirect(url_for("ArticlesWipView:images", id=article.id))
        warn(image_filename, image_content_type, len(image_bytes))
        caption = request.form.get("caption", "").strip()
        copyright = request.form.get("copyright", "").strip()

        image_file_object = create_file_object(
            content=image_bytes,
            original_filename=image_filename,
            content_type=image_content_type,
        )
        image_file_object.save()

        position = len(article.images)

        article_image = Image(
            caption=caption,
            copyright=copyright,
            content=image_file_object,
            owner=article.owner,
            article_id=article.id,
            position=position,
        )

        image_repo.add(article_image)
        # article.add_image(article_image)
        article_repo.update(article, auto_commit=False)
        db.session.commit()
        referrer_url = request.referrer or "/"
        redirect_url = referrer_url + "#last_image"
        return redirect(redirect_url)

    @route("/<int:article_id>/images/<int:image_id>")
    def image(self, article_id: int, image_id: int):
        article = cast("Article", self._get_model(article_id))
        image = next((im for im in article.images if im.id == image_id), None)
        if image is None:
            raise NotFound
        return redirect(image.url, code=301)

    @route("/<int:article_id>/images/<int:image_id>/delete", methods=["POST"])
    def delete_image(self, article_id: int, image_id: int):
        article = cast("Article", self._get_model(article_id))
        image = article.get_image(image_id)
        if not image:
            raise NotFound

        article.delete_image(image)
        if image.content:
            try:
                image.content.delete()
                warn(f"Success deleted file for Image {image_id}")
            except Exception as e:
                warn(f"Could not delete file {image_id}: {e}")

        db.session.delete(image)
        db.session.commit()

        return redirect(url_for("ArticlesWipView:images", id=article_id))

    @route("/<int:article_id>/images/<int:image_id>/move", methods=["POST"])
    def move_image(self, article_id: int, image_id: int):
        article = cast("Article", self._get_model(article_id))
        image = article.get_image(image_id)
        if not image:
            raise NotFound

        direction = request.form.get("direction")

        images = article.sorted_images
        assert [im.position for im in images] == list(range(len(images)))

        match direction:
            case "up":
                prev_image = images[image.position - 1]
                image.position -= 1
                prev_image.position += 1
            case "down":
                next_image = images[image.position + 1]
                image.position += 1
                next_image.position -= 1

        db.session.commit()

        return redirect(url_for("ArticlesWipView:images", id=article_id))


@register
def register_on_app(app: Flask) -> None:
    ArticlesWipView.register(app)
