# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from typing import cast

from flask import (
    Flask,
    flash,
    g,
    make_response,
    redirect,
    render_template,
    request,
    send_file,
)
from flask_classful import route
from flask_super.registry import register
from sqlalchemy_utils.types.arrow import arrow
from svcs.flask import container
from werkzeug.exceptions import NotFound

from app.flask.extensions import db
from app.flask.lib.constants import EMPTY_PNG
from app.flask.routing import url_for
from app.models.lifecycle import PublicationStatus
from app.modules.wip.models import ComImage, Communique, CommuniqueRepository
from app.services.blobs import BlobService
from app.settings.constants import MAX_IMAGE_SIZE
from app.signals import communique_published, communique_unpublished, communique_updated

from ._base import BaseWipView
from ._forms import CommuniqueForm
from ._table import BaseTable


class CommuniquesTable(BaseTable):
    id = "communiques-table"

    def __init__(self, q="") -> None:
        super().__init__(Communique, q)

    def url_for(self, obj, _action="get", **kwargs):
        return url_for(f"CommuniquesWipView:{_action}", id=obj.id, **kwargs)

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


class CommuniquesWipView(BaseWipView):
    name = "communiques"

    model_class = Communique
    repo_class = CommuniqueRepository
    table_class = CommuniquesTable
    form_class = CommuniqueForm
    doc_type = "communique"

    route_base = "communiques"
    path = "/wip/communiques/"

    # UI
    icon = "megaphone"

    label_main = "Com'room: communiqués"
    label_list = "Liste des communiqués"
    label_new = "Créer un communiqué"
    label_edit = "Modifier le communiqué"
    label_view = "Voir le communiqué"

    table_id = "communique-table-body"

    msg_delete_ok = "Le communiqué a été supprimé"
    msg_delete_ko = "Vous n'êtes pas autorisé à supprimer ce communiqué"

    def _post_update_model(self, model: Communique) -> None:
        if not model.status:
            model.status = PublicationStatus.DRAFT
            model.published_at = arrow.now("Europe/Paris")
            if g.user.organisation_id:
                model.publisher_id = g.user.organisation_id
        communique_updated.send(model)

    def publish(self, id: int):
        repo = self._get_repo()
        communique = cast("Communique", self._get_model(id))
        communique.status = PublicationStatus.PUBLIC
        repo.update(communique, auto_commit=True)
        flash("Le communiqué a été publié")
        communique_published.send(communique)
        return redirect(self._url_for("index"))

    def unpublish(self, id: int):
        repo = self._get_repo()
        communique = cast("Communique", self._get_model(id))
        communique.status = PublicationStatus.DRAFT
        repo.update(communique, auto_commit=True)
        flash("Le communiqué a été dépublié")
        communique_unpublished.send(communique)
        return redirect(self._url_for("index"))

    @route("/<int:id>/images/", methods=["GET", "POST"])
    def images(self, id: int):
        communique = cast("Communique", self._get_model(id))

        action = request.form.get("_action")
        if action == "cancel":
            return redirect(self._url_for("index"))

        if action == "add-image":
            return self._add_image(communique)

        title = f"Images pour le communiqué - {communique.title}"
        self.update_breadcrumbs(label=communique.title)

        ctx = {
            "title": title,
            "communique": communique,
        }

        html = render_template("wip/communique/images.j2", **ctx)
        return html

    def _add_image(self, communique: Communique):
        communique_repo = self._get_repo()
        blob_service = container.get(BlobService)

        image = request.files["image"]
        caption = request.form.get("caption", "").strip()
        copyright = request.form.get("copyright", "").strip()

        image_bytes = image.read()
        if not image_bytes:
            flash("L'image est vide")
            return redirect(url_for("CommuniquesWipView:images", id=communique.id))
        if len(image_bytes) >= MAX_IMAGE_SIZE:
            flash("L'image est trop volumineuse")
            return redirect(url_for("CommuniquesWipView:images", id=communique.id))

        blob = blob_service.save(image_bytes)

        image = ComImage(
            caption=caption,
            copyright=copyright,
            blob_id=blob.id,
            owner=communique.owner,
        )
        communique.add_image(image)
        communique_repo.update(communique, auto_commit=True)
        referrer_url = request.referrer or "/"
        redirect_url = referrer_url + "#last_image"
        return redirect(redirect_url)

    @route("/<int:communique_id>/images/<int:image_id>")
    def image(self, communique_id: int, image_id: int):
        communique = cast("Communique", self._get_model(communique_id))
        for image in communique.images:
            if image.id == image_id:
                break
        else:
            raise NotFound

        blob_service = container.get(BlobService)
        try:
            blob_path = blob_service.get_path(image.blob_id)
            return send_file(blob_path)
        except FileNotFoundError:
            response = make_response(EMPTY_PNG)
            response.headers.set("Content-Type", "image/png")
            return response

    @route("/<int:communique_id>/images/<int:image_id>/delete", methods=["POST"])
    def delete_image(self, communique_id: int, image_id: int):
        communique = cast("Communique", self._get_model(communique_id))
        image = communique.get_image(image_id)
        if not image:
            raise NotFound

        communique.delete_image(image)
        db.session.delete(image)
        db.session.commit()

        return redirect(url_for("CommuniquesWipView:images", id=communique_id))

    @route("/<int:communique_id>/images/<int:image_id>/move", methods=["POST"])
    def move_image(self, communique_id: int, image_id: int):
        communique = cast("Communique", self._get_model(communique_id))
        image = communique.get_image(image_id)
        if not image:
            raise NotFound

        direction = request.form.get("direction")

        images = communique.sorted_images
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

        return redirect(url_for("CommuniquesWipView:images", id=communique_id))


@register
def register_on_app(app: Flask) -> None:
    CommuniquesWipView.register(app)
