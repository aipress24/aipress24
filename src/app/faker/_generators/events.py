# Copyright (c) 2021-2024 - Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

import random

import app.settings.vocabularies as voc
from app.faker._constants import LOCATION, POST_CATEGORIES, POST_IMAGES
from app.models.content.events import EVENT_CLASSES, Event
from app.models.lifecycle import PublicationStatus

from .base import BaseGenerator


class EventGenerator(BaseGenerator):
    def make_obj(self) -> Event:
        users = self.repository["users"]

        cls = random.choice(EVENT_CLASSES)
        event = cls()
        owner = random.choice(users)
        event.owner_id = owner.id
        event.status = random.choice(list(PublicationStatus))
        event.title = self.generate_short_title()
        event.summary = self.text_faker.text(random.randint(1, 2))
        event.content = self.generate_html(1, 3)

        event.location = random.choice(LOCATION)
        event.category = random.choice(POST_CATEGORIES)
        event.sector = random.choice(voc.get_sectors())
        event.image_url = random.choice(POST_IMAGES)

        event.start_date = self.generate_date(future=True)
        event.end_date = event.start_date

        id = random.randint(1, 14)
        event.logo_url = f"/static/tmp/logos/{id}.png"

        return event
