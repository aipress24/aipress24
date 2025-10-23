# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from attr import define

from app.flask.lib.pywire import Component, component
from app.models.meta import get_meta_attr
from app.modules.events.models import EventPost

LOGO_URL = "https://aipress24.demo.abilian.com/static/tmp/logos/1.png"
HOUR_FMT = "HH:mm"


@component
@define
class EventCard(Component):
    event: EventPost

    def opening_hours(self) -> str:
        start_hour = self.event.start_date.format(HOUR_FMT)
        end_hour = self.event.end_date.format(HOUR_FMT)
        if self.event.start_date == self.event.end_date:
            return f"à {start_hour}"
        return f"de {start_hour} à {end_hour}"

    def __attrs_post_init__(self) -> None:
        # HACK
        d = self.event.__dict__
        d["author"] = self.event.owner
        d["organisation_image_url"] = LOGO_URL
        d["type_id"] = get_meta_attr(self.event, "type_id", "")
        d["type_label"] = get_meta_attr(self.event, "type_label", "")
        d["opening"] = self.opening_hours()
