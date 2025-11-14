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
from app.modules.wip.models.eventroom import Event, EventImage
from app.modules.wip.models.eventroom.repositories import EventRepository
from app.services.blobs import BlobService
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
        event.status = PublicationStatus.PUBLIC
        repo.update(event, auto_commit=False)
        event_published.send(event)
        db.session.commit()
        flash("L'événement a été publié")
        return redirect(self._url_for("index"))

    def unpublish(self, id: int):
        repo = self._get_repo()
        event = cast("Event", self._get_model(id))
        event.status = PublicationStatus.DRAFT
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
        blob_service = container.get(BlobService)

        image = request.files["image"]
        caption = request.form.get("caption", "").strip()
        copyright = request.form.get("copyright", "").strip()

        image_bytes = image.read()
        if not image_bytes:
            flash("L'image est vide")
            return redirect(url_for("EventsWipView:images", id=event.id))
        if len(image_bytes) >= MAX_IMAGE_SIZE:
            flash("L'image est trop volumineuse")
            return redirect(url_for("EventsWipView:images", id=event.id))

        blob = blob_service.save(image_bytes)

        image = EventImage(
            caption=caption,
            copyright=copyright,
            blob_id=blob.id,
            owner=event.owner,
        )
        event.add_image(image)
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

        blob_service = container.get(BlobService)
        try:
            blob_path = blob_service.get_path(image.blob_id)
            return send_file(blob_path)
        except FileNotFoundError:
            response = make_response(EMPTY_PNG)
            response.headers.set("Content-Type", "image/png")
            return response

    @route("/<int:event_id>/images/<int:image_id>/delete", methods=["POST"])
    def delete_image(self, event_id: int, image_id: int):
        event = cast("Event", self._get_model(event_id))
        image = event.get_image(image_id)
        if not image:
            raise NotFound

        event.delete_image(image)
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
