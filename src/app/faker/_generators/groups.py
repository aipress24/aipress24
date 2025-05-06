# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

import random

from app.faker._constants import COVER_IMAGES
from app.faker._geo import fake_geoloc
from app.modules.swork.models import Group

from .base import BaseGenerator, faker


class GroupGenerator(BaseGenerator):
    def make_obj(self) -> Group:
        users = self.repository["users"]

        group = Group()
        group.name = faker.company()
        group.description = self.generate_html(min_sentences=1, max_sentences=3)
        group.owner_id = random.choice(users).id
        group.privacy = random.choice(["private", "semi-public", "public"])

        id = random.randint(1, 14)
        group.logo_url = f"/static/tmp/logos/{id}.png"
        group.cover_image_url = random.choice(COVER_IMAGES)

        fake_geoloc(group)

        return group
