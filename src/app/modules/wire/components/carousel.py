# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from attr import frozen
from svcs.flask import container

from app.flask.lib.pywire import Component, component
from app.flask.lib.types import JSON
from app.modules.wip.models import ArticleRepository, Image
from app.modules.wire.models import ArticlePost


@component
@frozen
class Carousel(Component):
    post: ArticlePost
    img_class: str = "min-h-64"

    @property
    def alpine_data(self) -> JSON:
        slides = self.get_slides()
        return {"slides": slides}

    @property
    def slides(self) -> list[dict[str, str | int]]:
        return self.get_slides()

    def get_slides(self):
        try:
            article_id = self.post.newsroom_id
            repo = container.get(ArticleRepository)
            article = repo.get(article_id)
        except AttributeError:
            article = self.post

        try:
            images: list[Image] = article.sorted_images
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

        else:
            return [
                {
                    "id": i,
                    "imgSrc": image.url,
                    "imgAlt": image.caption,
                }
                for i, image in enumerate(images)
            ]
