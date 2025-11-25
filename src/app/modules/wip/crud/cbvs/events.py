# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from io import BytesIO
from typing import cast

import advanced_alchemy
from advanced_alchemy.types.file_object import FileObject
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
from app.logging import warn
from app.models.lifecycle import PublicationStatus
from app.modules.wip.models.eventroom import (
    Event,
    EventImage,
    EventImageRepository,
    EventRepository,
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


class EventsTable(BaseTable):
    id = "events-table"

    def __init__(self, q="") -> None:
        super().__init__(Event, q)

    def url_for(self, obj, _action="get", **kwargs):
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
        if not model.status:
            model.status = PublicationStatus.DRAFT
            model.published_at = arrow.now("Europe/Paris")
            if g.user.organisation_id:
                model.publisher_id = g.user.organisation_id
        event_updated.send(model)

    def publish(self, id: int):
        repo = self._get_repo()
        event = cast("Event", self._get_model(id))

        # Use business method to publish (includes validation)
        try:
            publisher_id = g.user.organisation_id if g.user.organisation_id else None
            event.publish(publisher_id=publisher_id)
        except ValueError as e:
            flash(str(e), "error")
            return redirect(self._url_for("edit", id=id))

        repo.update(event, auto_commit=False)
        event_published.send(event)
        db.session.commit()
        flash("L'événement a été publié")
        return redirect(self._url_for("index"))

    def unpublish(self, id: int):
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
        if action == "cancel":
            return redirect(self._url_for("index"))

        if action == "add-image":
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
        image_repo = EventImageRepository(session=db.session)

        image = request.files["image"]
        image_bytes = image.read()

        if not image_bytes:
            flash("L'image est vide")
            return redirect(url_for("EventsWipView:images", id=event.id))
        if len(image_bytes) >= MAX_IMAGE_SIZE:
            flash("L'image est trop volumineuse")
            return redirect(url_for("EventsWipView:images", id=event.id))

        image_filename = image.filename or "noname.jpg"
        image_content_type = image.content_type or "application/binary"
        warn(image_filename, image_content_type, len(image_bytes))
        caption = request.form.get("caption", "").strip()
        copyright = request.form.get("copyright", "").strip()

        image_file_object = FileObject(
            content=image_bytes,
            filename=image_filename,
            content_type=image_content_type,
            backend="s3",
        )
        image_file_object.save()

        event_image = EventImage(
            caption=caption,
            copyright=copyright,
            content=image_file_object,
            owner=event.owner,
            event_id=event.id,
        )

        image_repo.add(event_image)
        event.add_image(event_image)
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
