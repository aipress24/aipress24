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
from sqlalchemy_utils.types.arrow import arrow
from werkzeug.exceptions import NotFound

from app.flask.extensions import db
from app.flask.lib.constants import EMPTY_PNG
from app.flask.routing import url_for
from app.lib.file_object_utils import create_file_object
from app.lib.image_utils import extract_image_from_request
from app.logging import warn
from app.models.lifecycle import PublicationStatus
from app.modules.bw.bw_activation.user_utils import (
    can_user_publish_for,
    get_validated_client_orgs_for_user,
)
from app.modules.wip.models.eventroom import (
    Event,
    EventImage,
    EventImageRepository,
    EventRepository,
)
from app.modules.wip.services.pr_notifications import (
    absolute_url_for,
    notify_client_of_pr_publication,
)
from app.settings.constants import MAX_IMAGE_SIZE
from app.signals import (
    event_published,
    event_unpublished,
    event_updated,
)

from ._base import BaseWipView
from ._forms import EventForm
from ._table import BaseTable

if TYPE_CHECKING:
    from app.lib.image_utils import UploadedImageData


class EventsTable(BaseTable):
    id = "events-table"

    def __init__(self, q="") -> None:
        super().__init__(Event, q)

    def url_for(self, obj, _action="get", **kwargs):  # type: ignore[override]
        return url_for(f"EventsWipView:{_action}", id=obj.id, **kwargs)

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


class EventsWipView(BaseWipView):
    name = "events"

    model_class = Event
    repo_class = EventRepository
    table_class = EventsTable
    form_class = EventForm
    doc_type = "event"

    route_base = "events"
    path = "/wip/events/"

    # UI
    icon = "calendar"

    label_main = "Evénements"
    label_list = "Liste des événements"
    label_new = "Créer un événement"
    label_edit = "Modifier l'événement"
    label_view = "Voir l'événement"

    table_id = "events-table-body"

    msg_delete_ok = "L'événement a été supprimé"
    msg_delete_ko = "Vous n'êtes pas autorisé à supprimer cet événement"

    def _post_update_model(self, model: Event) -> None:
        # Sanity-check publisher_id set by the form; unauthorized choices
        # fall back silently to the user's own organisation.
        if model.publisher_id and not can_user_publish_for(g.user, model.publisher_id):
            model.publisher_id = g.user.organisation_id  # type: ignore[assignment]
        if not model.publisher_id and g.user.organisation_id:
            model.publisher_id = g.user.organisation_id

        if not model.status:
            model.status = PublicationStatus.DRAFT  # type: ignore[assignment]
            model.published_at = arrow.now("Europe/Paris")  # type: ignore[assignment,union-attr]
        event_updated.send(model)

    def _view_ctx(self, model=None, form=None, mode="edit", title=""):
        if not form:
            form = self.form_class(obj=model)
        self._make_publisher_choices(form)
        return super()._view_ctx(model, form, mode, title)

    def _make_publisher_choices(self, form) -> None:
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
        event = cast("Event", self._get_model(id))

        publisher_id = event.publisher_id or g.user.organisation_id or None
        if publisher_id and not can_user_publish_for(g.user, publisher_id):
            flash(
                "Vous n'êtes pas autorisé à publier pour cette organisation.",
                "error",
            )
            return redirect(self._url_for("edit", id=id))

        try:
            event.publish(publisher_id=publisher_id)
        except ValueError as e:
            flash(str(e), "error")
            return redirect(self._url_for("edit", id=id))

        repo.update(event, auto_commit=False)
        event_published.send(event)
        db.session.commit()

        if (
            event.publisher
            and g.user.organisation_id
            and event.publisher_id != g.user.organisation_id
        ):
            try:
                notify_client_of_pr_publication(
                    author=g.user,
                    client_org=event.publisher,
                    content_type="événement",
                    content_title=event.titre,
                    content_url=absolute_url_for("EventsWipView:get", id=event.id),
                )
            except Exception as exc:  # noqa: BLE001
                warn(f"PR publication notif failed (event {event.id}): {exc}")

        flash("L'événement a été publié")
        return redirect(self._url_for("index"))

    def unpublish(self, id):
        repo = self._get_repo()
        event = cast("Event", self._get_model(id))

        # Use business method to unpublish (includes validation)
        try:
            event.unpublish()
        except ValueError as e:
            flash(str(e), "error")
            return redirect(self._url_for("get", id=id))

        repo.update(event, auto_commit=False)
        event_unpublished.send(event)
        db.session.commit()
        flash("L'événement a été dépublié")
        return redirect(self._url_for("index"))

    @route("/<int:id>/images/", methods=["GET", "POST"])
    def images(self, id: int):
        event = cast("Event", self._get_model(id))

        action = request.form.get("_action")
        match action:
            case "cancel":
                return redirect(self._url_for("index"))
            case "add-image":
                return self._add_image(event)

        title = f"Images pour l'événement - {event.title}"
        self.update_breadcrumbs(label=event.title)

        ctx = {
            "title": title,
            "event": event,
        }

        html = render_template("wip/event/images.j2", **ctx)
        return html

    def _add_image(self, event: Event):
        event_repo = self._get_repo()
        image_repo = EventImageRepository(session=db.session)  # type: ignore[arg-type]

        # Handle both regular file upload and base64 data URL from cropper
        result: UploadedImageData | None = extract_image_from_request(
            file_storage=request.files.get("image"),
            data_url=request.form.get("image"),
            orig_filename=request.form.get("image_filename") or None,
        )

        if result is None:
            flash("L'image est vide")
            return redirect(url_for("EventsWipView:images", id=event.id))

        image_bytes = result.bytes
        image_filename = result.filename
        image_content_type = result.content_type
        if len(image_bytes) >= MAX_IMAGE_SIZE:
            flash("L'image est trop volumineuse")
            return redirect(url_for("EventsWipView:images", id=event.id))
        caption = request.form.get("caption", "").strip()
        copyright = request.form.get("copyright", "").strip()

        image_file_object = create_file_object(
            content=image_bytes,
            original_filename=image_filename,
            content_type=image_content_type,
        )
        image_file_object.save()

        position = len(event.images)

        event_image = EventImage(
            caption=caption,
            copyright=copyright,
            content=image_file_object,
            owner=event.owner,
            event_id=event.id,
            position=position,
        )

        image_repo.add(event_image)
        # event.add_image(event_image)
        event_repo.update(event, auto_commit=False)
        db.session.commit()
        referrer_url = request.referrer or "/"
        redirect_url = referrer_url + "#last_image"
        return redirect(redirect_url)

    @route("/<int:event_id>/images/<int:image_id>")
    def image(self, event_id: int, image_id: int):
        event = cast("Event", self._get_model(event_id))
        for image in event.images:
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

    @route("/<int:event_id>/images/<int:image_id>/delete", methods=["POST"])
    def delete_image(self, event_id: int, image_id: int):
        event = cast("Event", self._get_model(event_id))
        image = event.get_image(image_id)
        if not image:
            raise NotFound

        event.delete_image(image)
        if image.content:
            try:
                image.content.delete()
                warn(f"Success deleted file for Image {image_id}")
            except Exception as e:
                warn(f"Could not delete file {image_id}: {e}")

        db.session.delete(image)
        db.session.commit()

        return redirect(url_for("EventsWipView:images", id=event_id))

    @route("/<int:event_id>/images/<int:image_id>/move", methods=["POST"])
    def move_image(self, event_id: int, image_id: int):
        event = cast("Event", self._get_model(event_id))
        image = event.get_image(image_id)
        if not image:
            raise NotFound

        direction = request.form.get("direction")

        images = event.sorted_images
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

        return redirect(url_for("EventsWipView:images", id=event_id))


@register
def register_on_app(app: Flask) -> None:
    EventsWipView.register(app)
