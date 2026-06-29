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
from werkzeug.exceptions import Forbidden, NotFound

from app.flask.extensions import db
from app.flask.lib.templates import templated
from app.flask.routing import url_for
from app.lib.base62 import base62
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


def _absolute_url_for(endpoint: str, **values) -> str:
    """Build an absolute URL for outbound notifications.

    Mirrors the sujet helper (`cbvs/sujets.py`) — duplicated to keep
    the import direction clean (this module already imports from many
    others ; pulling the helper would add a circular hop via sujet's
    rédac chef plumbing).
    """
    from flask import current_app, url_for as _url_for

    domain = str(current_app.config.get("SERVER_NAME") or "aipress24.com")
    protocol = "http" if domain.startswith("127.") else "https"
    path = _url_for(endpoint, **values)
    return f"{protocol}://{domain}{path}"


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

# Ticket #0154: surface the step-nav bar (carried over from #0151
# on Avis d'enquête) at the top and bottom of the Voir / Modifier
# pages. The base VIEW_TEMPLATE / UPDATE_TEMPLATE in _base.py is
# shared across several CBVs we shouldn't disturb ; subclass-level
# wrappers keep the change scoped.
# language=jinja2
_ARTICLE_VOIR_TEMPLATE = """
{% extends "wip/layout/_base.j2" %}
{% from "wip/_step_nav_simple.j2" import step_nav_simple %}
{% block body_content %}
  {{ step_nav_simple(article, "ArticlesWipView", "voir", "articles") }}
  {{ form_rendered|safe }}
  {{ extra_view_html|safe }}
  {{ step_nav_simple(article, "ArticlesWipView", "voir", "articles") }}
{% endblock %}
"""

# language=jinja2
_ARTICLE_MODIFIER_TEMPLATE = """
{% extends "wip/layout/_base.j2" %}
{% from "wip/_step_nav_simple.j2" import step_nav_simple %}
{% block body_content %}
  {{ step_nav_simple(article, "ArticlesWipView", "modifier", "articles") }}
  {{ form_rendered|safe }}
  {{ step_nav_simple(article, "ArticlesWipView", "modifier", "articles") }}
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
            # Ticket #0195 — « Justificatif » : notifier les
            # participants à une enquête que l'article publié les
            # concerne. Apparait uniquement sur les articles publiés
            # car la cible (lecteur potentiel) doit pouvoir cliquer.
            actions.append(
                {
                    "label": "Justificatif",
                    "url": self.url_for(item, "notify"),
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

    @templated(_ARTICLE_VOIR_TEMPLATE)
    def get(self, id):
        """Step « Voir » — wrapped with the #0154 step-nav bar."""
        model = self._get_model(id)
        title = f"{self.label_view} '{model.title}'"
        ctx = self._view_ctx(model, title=title, mode="view")
        ctx["article"] = model
        return ctx

    @templated(_ARTICLE_MODIFIER_TEMPLATE)
    def edit(self, id):
        """Step « Modifier » — wrapped with the #0154 step-nav bar."""
        model = self._get_model(id)
        title = f"{self.label_edit} '{model.title}'"
        ctx = self._view_ctx(model, title=title)
        ctx["article"] = model
        return ctx

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

    @route("/<int:id>/notify/", methods=["GET", "POST"])
    def notify(self, id: int):
        """Ticket #0195 — « Justificatif » action : notify enquête
        participants of a publication.

        GET : render the form with the journalist's avis d'enquêtes
        and (if one is picked) its contacts.
        POST : send mail + cloche to selected recipients.
        """
        # Lazy imports : keep the article view free of newsroom plumbing
        # at cold start.
        from app.modules.wip.services.newsroom.justificatif_notification import (
            list_avis_contacts,
            list_journalist_avis_enquetes,
            notify_avis_participants_of_justificatif,
        )

        article = cast("Article", self._get_model(id))
        user = g.user

        # Only the article's author can trigger justificatif notifications.
        # Without this guard any WIP user could POST/GET for any article
        # id and either spam recipients in the author's name or
        # reconnoitre the journalist's avis list.
        if getattr(article, "owner_id", None) != user.id:
            raise Forbidden

        if request.method == "POST":
            try:
                avis_id = int(request.form.get("avis_enquete_id", "0"))
            except ValueError:
                avis_id = 0
            recipient_ids: list[int] = []
            for raw in request.form.getlist("recipient_user_id"):
                try:
                    recipient_ids.append(int(raw))
                except ValueError:
                    continue

            if not avis_id or not recipient_ids:
                flash(
                    "Choisissez une enquête et au moins un destinataire.",
                    "error",
                )
                return redirect(self._url_for("notify", id=article.id))

            from app.modules.wip.models.newsroom.avis_enquete import (
                AvisEnquete,
            )

            avis = db.session.get(AvisEnquete, avis_id)
            if avis is None or avis.owner_id != user.id:
                flash("Enquête introuvable.", "error")
                return redirect(self._url_for("index"))

            # The public /wire/<id> URL uses the wire ArticlePost id,
            from app.modules.wire.models import ArticlePost

            article_post = (
                db.session.query(ArticlePost)
                .filter(ArticlePost.newsroom_id == article.id)
                .first()
            )
            post_id = article_post.id if article_post is not None else article.id

            notified = notify_avis_participants_of_justificatif(
                article=article,
                avis_enquete=avis,
                recipient_user_ids=recipient_ids,
                journalist=user,
                article_url=_absolute_url_for("wire.item", id=base62.encode(post_id)),
            )
            # Commit before redirect. The service only flushes the
            # counter increment + in-app notifications ; without this
            # commit, the request teardown (`session.remove()`) rolls
            # everything back. The flash would claim success while the
            # DB stayed unchanged — breaking the journalist's
            # rémunération calc which feeds off this counter.
            db.session.commit()
            flash(
                f"{notified} participant(s) notifié(s) du justificatif.",
                "success",
            )
            return redirect(self._url_for("index"))

        # GET — render the picker.
        avis_list = list_journalist_avis_enquetes(user.id)
        selected_avis_id_raw = request.args.get("avis_enquete_id", "")
        try:
            selected_avis_id = int(selected_avis_id_raw)
        except ValueError:
            selected_avis_id = 0
        contacts = list_avis_contacts(selected_avis_id) if selected_avis_id else []
        # Breadcrumbs : the base WIP layout reads them from the request
        # context — `update_phase_breadcrumbs` populates the standard
        # « Work > Articles > <title> > <phase> » trail.
        self.update_phase_breadcrumbs(article, "Justificatif")
        return render_template(
            "wip/article/notify_justificatif.j2",
            title=f"Notifier les participants — {article.title}",
            article=article,
            avis_list=avis_list,
            selected_avis_id=selected_avis_id,
            contacts=contacts,
        )

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
        self.update_phase_breadcrumbs(article, "Images")

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
                # pyrefly: ignore [bad-index]
                prev_image = images[image.position - 1]
                image.position -= 1
                prev_image.position += 1
            case "down":
                # pyrefly: ignore [bad-index]
                next_image = images[image.position + 1]
                image.position += 1
                next_image.position -= 1

        db.session.commit()

        return redirect(url_for("ArticlesWipView:images", id=article_id))


@register
def register_on_app(app: Flask) -> None:
    ArticlesWipView.register(app)
