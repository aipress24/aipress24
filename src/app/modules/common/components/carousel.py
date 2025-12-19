# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from attr import frozen
from svcs.flask import container

from app.flask.lib.pywire import Component, component
from app.flask.lib.types import JSON
from app.modules.common.components.post_card import (
    ArticleVM,
    PressReleaseVM,
)
from app.modules.events.models import EventPost
from app.modules.events.views._common import EventDetailVM as EventVM
from app.modules.wip.models import (
    ArticleRepository,
    ComImage,
    CommuniqueRepository,
    EventImage,
    EventRepository,
    Image,
)
from app.modules.wire.models import (
    ArticlePost,
    PressReleasePost,
)


@component
@frozen
class Carousel(Component):
    post: (
        ArticlePost
        | PressReleasePost
        | ArticleVM
        | PressReleaseVM
        | EventPost
        | EventVM
    )
    img_class: str = "min-h-64"

    @property
    def alpine_data(self) -> JSON:
        slides = self.get_slides()
        return {"slides": slides}

    @property
    def slides(self) -> list[dict[str, str | int]]:
        return self.get_slides()

    def get_slides(self):
        info_type = self.post.__class__.__name__
        # if isinstance(self.post, (ArticlePost, ArticleVM)):
        if info_type == "ArticleVM":
            try:
                info_id = self.post.newsroom_id
                repo = container.get(ArticleRepository)
                info = repo.get(info_id)
            except AttributeError:
                info = self.post
        # elif isinstance(self.post, (PressReleasePost, PressReleaseVM)):
        elif info_type == "PressReleaseVM":
            try:
                info_id = self.post.newsroom_id
                repo = container.get(CommuniqueRepository)
                info = repo.get(info_id)
            except AttributeError:
                info = self.post
        elif info_type == "EventVM":
            try:
                info_id = self.post.eventroom_id
                repo = container.get(EventRepository)
                info = repo.get(info_id)
            except AttributeError:
                info = self.post
        else:
            msg = f"expected ArticleVM or PressReleaseVM, not {self.post!r}"
            raise TypeError(msg)

        try:
            images: list[Image | ComImage | EventImage] = info.sorted_images
        except AttributeError:
            images = []

        if not images:
            return [
                {
                    "id": 0,
                    "imgSrc": "/static/img/gray-texture.png",
                    "imgAlt": "Placeholder image",
                },
            ]

        return [
            {
                "id": i,
                "imgSrc": image.url,
                "imgAlt": image.caption + " - " + image.copyright,
            }
            for i, image in enumerate(images)
        ]
