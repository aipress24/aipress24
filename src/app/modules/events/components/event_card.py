# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from attr import define

from app.flask.lib.pywire import Component, component
from app.models.meta import get_meta_attr
from app.modules.events.components.opening_hours import opening_hours
from app.modules.events.models import EventPost

LOGO_URL = "https://aipress24.demo.abilian.com/static/tmp/logos/1.png"


@component
@define
class EventCard(Component):
    event: EventPost

    def __attrs_post_init__(self) -> None:
        # HACK
        d = self.event.__dict__
        d["author"] = self.event.owner
        d["organisation_image_url"] = LOGO_URL
        d["type_id"] = get_meta_attr(self.event, "type_id", "")
        d["type_label"] = get_meta_attr(self.event, "type_label", "")
        d["opening"] = opening_hours(self.event.start_datetime, self.event.end_datetime)
