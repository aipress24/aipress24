# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from arrow import now
from sqlalchemy import select

from app.constants import LOCAL_TZ
from app.flask.extensions import db
from app.models.lifecycle import PublicationStatus
from app.modules.events.models import EventPost
from app.modules.wip.models.eventroom import Event
from app.signals import (
    event_published,
    event_unpublished,
    event_updated,
)


@event_published.connect
def on_publish_event(event: Event) -> None:
    print(f"Received 'Event published': {event.title}")
    post = get_post(event)
    if not post:
        post = EventPost()
        post.eventroom_id = event.id
        post.created_at = event.created_at
        post.published_at = now(LOCAL_TZ)

    post.status = PublicationStatus.PUBLIC

    update_post(post, event)

    db.session.add(post)
    db.session.flush()


@event_unpublished.connect
def on_unpublish_event(event: Event) -> None:
    print(f"Event unpublished: {event.title}")
    post = get_post(event)
    if not post:
        return
    post.status = PublicationStatus.DRAFT

    db.session.add(post)
    db.session.flush()


@event_updated.connect
def on_update_event(event: Event) -> None:
    print(f"Received 'Event updated': {event.title}")
    post = get_post(event)
    if not post:
        # Article not published yet, nothing to do
        return

    print(f"Updating post: {post}")
    update_post(post, event)
    post.last_updated_at = now(LOCAL_TZ)

    db.session.add(post)
    db.session.flush()


def event_type_to_category(event_type: str) -> str:
    first_part = event_type.split("/", maxsplit=1)[0]
    return first_part.strip().replace(" ", "_").lower()


def update_post(
    post: EventPost,
    info: Event,
) -> None:
    post.title = info.title
    post.summary = info.chapo
    post.content = info.contenu
    post.owner_id = info.owner_id

    # # TODO: remove
    # images = info.sorted_images
    # if images:
    #     image = images[0]
    #     post.image_id = image.id
    #     post.image_url = image.url
    #     post.image_caption = image.caption
    #     post.image_copyright = image.copyright
    # else:
    #     post.image_id = None
    #     post.image_url = ""
    #     post.image_caption = ""
    #     post.image_copyright = ""

    # Metadata
    post.start_time = info.start_time
    post.end_time = info.end_time
    # FIXME
    post.start_date = info.start_time
    post.end_date = info.end_time

    # post.location = info.location
    post.address = info.address
    post.pays_zip_ville = info.pays_zip_ville
    post.pays_zip_ville_detail = info.pays_zip_ville_detail

    post.genre = info.event_type
    post.sector = info.sector
    post.category = event_type_to_category(info.event_type)

    post.url = info.url
    post.language = info.language

    # post.section = info.section
    # post.topic = info.topic
    # post.geo_localisation = info.geo_localisation


def get_post(info: Event) -> EventPost | None:
    stmt = select(EventPost).where(EventPost.eventroom_id == info.id)
    result = db.session.execute(stmt)
    post = result.scalar_one_or_none()
    return post
