# Copyright (c) 2021-2024 - Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

import random
from typing import cast

import app.settings.vocabularies as voc
from app.faker._constants import POST_IMAGES
from app.models.lifecycle import PublicationStatus
from app.modules.biz.models import EditorialProduct
from app.services.roles import Role, has_role

from .base import BaseGenerator
from .util import random_wikinews_article


class EditorialProductGenerator(BaseGenerator):
    def make_obj(self) -> EditorialProduct:
        users = self.repository["users"]
        journalists = [u for u in users if has_role(u, Role.PRESS_MEDIA)]

        product = EditorialProduct()

        # cast to work around a mypy bug
        product.status = cast(PublicationStatus, random.choice(list(PublicationStatus)))

        wikinews_d = random_wikinews_article()
        product.title = wikinews_d["title"]

        product.content = wikinews_d["html"]

        product.description = self.text_faker.text(2)
        product.image_url = random.choice(POST_IMAGES)
        product.product_type = random.choice(voc.PRODUCT_TYPES)

        product.owner_id = random.choice(journalists).id

        product.price = random.randint(1, 100) * 10

        # Generate metadata
        product.genre = random.choice(voc.get_genres())
        product.section = random.choice(voc.get_sections())
        product.sector = random.choice(voc.get_news_sectors())
        product.topic = random.choice(voc.get_topics())

        product.published_at = self.generate_date()

        return product
