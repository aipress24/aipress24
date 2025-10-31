# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from arrow import now
from sqlalchemy import select

from app.constants import LOCAL_TZ
from app.flask.extensions import db
from app.models.lifecycle import PublicationStatus
from app.modules.wip.models import Communique
from app.modules.wire.models import PressReleasePost
from app.signals import (
    communique_published,
    communique_unpublished,
    communique_updated,
)


@communique_published.connect
def on_publish_communique(communique: Communique) -> None:
    post = get_post(communique)
    if not post:
        post = PressReleasePost()
        post.newsroom_id = communique.id
        post.created_at = communique.created_at

    post.status = PublicationStatus.PUBLIC

    update_post(post, communique)

    db.session.add(post)
    db.session.commit()


@communique_unpublished.connect
def on_unpublish_communique(communique: Communique) -> None:
    post = get_post(communique)
    if not post:
        return
    post.status = PublicationStatus.DRAFT

    db.session.add(post)
    db.session.commit()


@communique_updated.connect
def on_update_communique(communique: Communique) -> None:
    post = get_post(communique)
    if not post:
        # Communique not published yet, nothing to do
        return

    update_post(post, communique)

    db.session.add(post)
    db.session.commit()


def update_post(post: PressReleasePost, info: Communique) -> None:
    post.title = info.title
    post.summary = info.chapo
    post.content = info.contenu
    post.owner_id = info.owner_id
    post.publisher_id = info.publisher_id

    # TODO: remove
    images = info.sorted_images
    if images:
        image = images[0]
        post.image_id = image.id
        post.image_url = image.url
        post.image_caption = image.caption
        post.image_copyright = image.copyright
    else:
        post.image_id = None
        post.image_url = ""
        post.image_caption = ""
        post.image_copyright = ""

    # Metadata
    post.genre = info.genre
    post.section = info.section
    post.topic = info.topic
    post.sector = info.sector
    post.geo_localisation = info.geo_localisation
    post.language = info.language

    post.address = info.address
    post.pays_zip_ville = info.pays_zip_ville
    post.pays_zip_ville_detail = info.pays_zip_ville_detail

    post.last_updated_at = now(LOCAL_TZ)
    post.published_at = info.published_at
    # Other possible publication dates:
    # post.published_at = now(LOCAL_TZ)


def get_post(info: Communique) -> PressReleasePost | None:
    stmt = select(PressReleasePost).where(PressReleasePost.newsroom_id == info.id)
    result = db.session.execute(stmt)
    post = result.scalar_one_or_none()
    return post
