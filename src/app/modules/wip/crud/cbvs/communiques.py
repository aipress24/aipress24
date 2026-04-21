# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from io import BytesIO
from typing import TYPE_CHECKING, cast

import advanced_alchemy
from flask import (
    Flask,
    flash,
    g,
    redirect,
    render_template,
    request,
    send_file,
)
from flask_classful import route
from flask_super.registry import register
from werkzeug.exceptions import NotFound

from app.flask.extensions import db
from app.flask.lib.constants import EMPTY_PNG
from app.flask.routing import url_for
from app.flask.sqla import get_obj
from app.lib.file_object_utils import create_file_object
from app.lib.image_utils import extract_image_from_request
from app.logging import warn
from app.models.lifecycle import PublicationStatus
from app.modules.bw.bw_activation.user_utils import (
    can_user_publish_for,
    get_validated_client_orgs_for_user,
)
from app.modules.wip.models import (
    ComImage,
    ComImageRepository,
    Communique,
    CommuniqueRepository,
)
from app.modules.wip.services.pr_notifications import (
    absolute_url_for,
    notify_client_of_pr_publication,
)
from app.settings.constants import MAX_IMAGE_SIZE
from app.signals import communique_published, communique_unpublished, communique_updated

from ._base import BaseWipView
from ._forms import CommuniqueForm
from ._table import BaseTable

if TYPE_CHECKING:
    from app.lib.image_utils import UploadedImageData


class CommuniquesTable(BaseTable):
    id = "communiques-table"

    def __init__(self, q="") -> None:
        super().__init__(Communique, q)

    def url_for(self, obj, _action="get", **kwargs):  # type: ignore[override]
        return url_for(f"CommuniquesWipView:{_action}", id=obj.id, **kwargs)

    def get_columns(self):
        return [
            {
                "name": "titre",
                "label": "Titre",
                "class": "max-w-0 w-full truncate",
            },
            {
                "name": "status",
                "label": "Statut",
            },
            {
                "name": "published_at",
                "label": "Publication",
                "class": "max-w-48 truncate",
            },
            {
                "name": "$actions",
                "label": "",
            },
        ]

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

    def _get_model(self, id):
        """Override to handle base62 encoded IDs from URLs."""
        return get_obj(id, self.model_class)

    def _post_update_model(self, model: Communique) -> None:
        # Validate publisher_id: if the user selected a client org they are
        # not authorized to publish for, warn but DO NOT silently reset.
        # The publish() step will enforce the auth and show an explicit error.
        # Otherwise a draft saved before the partnership is active ends up
        # attributed to the wrong org forever (should not happen very often).
        if model.publisher_id and not can_user_publish_for(g.user, model.publisher_id):
            warn(
                f"Communique {model.id}: user {g.user.id} selected publisher_id="
                f"{model.publisher_id} but can_user_publish_for is False. "
                "Keeping the value so the user sees the error at publish time."
            )
        if not model.publisher_id and g.user.organisation_id:
            model.publisher_id = g.user.organisation_id

        if not model.status:
            model.status = PublicationStatus.DRAFT  # type: ignore[assignment]
        communique_updated.send(model)

    def _view_ctx(self, model=None, form=None, mode="edit", title=""):
        if not form:
            form = self.form_class(obj=model)
        self._make_publisher_choices(form)
        return super()._view_ctx(model, form, mode, title)

    def _make_publisher_choices(self, form) -> None:
        """Populate the `publisher_id` select with the user's org + validated
        clients (for PR agency users)."""
        if not hasattr(form, "publisher_id"):
            return
        choices = []
        user = g.user
        own_org = getattr(user, "organisation", None)
        if user.organisation_id and own_org is not None:
            choices.append((user.organisation_id, f"Mon organisation — {own_org.name}"))
        for client_org in get_validated_client_orgs_for_user(user):
            choices.append((client_org.id, client_org.name))
        form.publisher_id.choices = choices

    def publish(self, id):
        repo = self._get_repo()
        communique = cast("Communique", self._get_model(id))

        publisher_id = communique.publisher_id or g.user.organisation_id or None
        if publisher_id and not can_user_publish_for(g.user, publisher_id):
            flash(
                "Vous n'êtes pas autorisé à publier pour cette organisation.",
                "error",
            )
            return redirect(self._url_for("edit", id=id))

        try:
            communique.publish(publisher_id=publisher_id)
        except ValueError as e:
            flash(str(e), "error")
            return redirect(self._url_for("edit", id=id))

        repo.update(communique, auto_commit=False)
        communique_published.send(communique)
        db.session.commit()

        # Notify the client's BW owner when an agency publishes on behalf.
        if (
            communique.publisher
            and g.user.organisation_id
            and communique.publisher_id != g.user.organisation_id
        ):
            try:
                notify_client_of_pr_publication(
                    author=g.user,
                    client_org=communique.publisher,
                    content_type="communiqué",
                    content_title=communique.titre,
                    content_url=absolute_url_for(
                        "CommuniquesWipView:get", id=communique.id
                    ),
                )
            except Exception as exc:  # noqa: BLE001
                warn(f"PR publication notif failed (communique {communique.id}): {exc}")

        flash("Le communiqué a été publié")
        return redirect(self._url_for("index"))

    def unpublish(self, id):
        repo = self._get_repo()
        communique = cast("Communique", self._get_model(id))

        # Use business method to unpublish (includes validation)
        try:
            communique.unpublish()
        except ValueError as e:
            flash(str(e), "error")
            return redirect(self._url_for("get", id=id))

        repo.update(communique, auto_commit=False)
        communique_unpublished.send(communique)
        db.session.commit()
        flash("Le communiqué a été dépublié")
        return redirect(self._url_for("index"))

    @route("/<int:id>/images/", methods=["GET", "POST"])
    def images(self, id: int):
        communique = cast("Communique", self._get_model(id))

        action = request.form.get("_action")
        match action:
            case "cancel":
                return redirect(self._url_for("index"))
            case "add-image":
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
        image_repo = ComImageRepository(session=db.session)  # type: ignore[arg-type]

        # Handle both regular file upload and base64 data URL from cropper
        result: UploadedImageData | None = extract_image_from_request(
            file_storage=request.files.get("image"),
            data_url=request.form.get("image"),
            orig_filename=request.form.get("image_filename") or None,
        )

        if result is None:
            flash("L'image est vide")
            return redirect(url_for("CommuniquesWipView:images", id=communique.id))

        image_bytes = result.bytes
        image_filename = result.filename
        image_content_type = result.content_type
        if len(image_bytes) >= MAX_IMAGE_SIZE:
            flash("L'image est trop volumineuse")
            return redirect(url_for("CommuniquesWipView:images", id=communique.id))
        warn(image_filename, image_content_type, len(image_bytes))
        caption = request.form.get("caption", "").strip()
        copyright = request.form.get("copyright", "").strip()

        image_file_object = create_file_object(
            content=image_bytes,
            original_filename=image_filename,
            content_type=image_content_type,
        )
        image_file_object.save()

        position = len(communique.images)

        com_image = ComImage(
            caption=caption,
            copyright=copyright,
            content=image_file_object,
            owner=communique.owner,
            communique_id=communique.id,
            position=position,
        )

        image_repo.add(com_image)
        # communique.add_image(com_image)
        communique_repo.update(communique, auto_commit=False)
        db.session.commit()
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

        stored_file = image.content
        if stored_file:
            try:
                file_bytes = stored_file.get_content()
                file_like_object = BytesIO(file_bytes)
                mimetype = stored_file.content_type
                download_name = stored_file.filename
            except advanced_alchemy.exceptions.ImproperConfigurationError as e:
                warn(f"Image not found: {e}")
                file_like_object = BytesIO(EMPTY_PNG)
                mimetype = "image/png"
                download_name = "empty.png"
        else:
            file_like_object = BytesIO(EMPTY_PNG)
            mimetype = "image/png"
            download_name = "empty.png"

        return send_file(
            file_like_object, mimetype=mimetype, download_name=download_name
        )

    @route("/<int:communique_id>/images/<int:image_id>/delete", methods=["POST"])
    def delete_image(self, communique_id: int, image_id: int):
        communique = cast("Communique", self._get_model(communique_id))
        image = communique.get_image(image_id)
        if not image:
            raise NotFound

        communique.delete_image(image)
        if image.content:
            try:
                image.content.delete()
                warn(f"Success deleted file for ComImage {image_id}")
            except Exception as e:
                warn(f"Could not delete file {image_id}: {e}")
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
