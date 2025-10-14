# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from attr import define

from app.flask.lib.pywire import Component, component
from app.modules.events.models import EventPost


@component
@define
class EventList(Component):
    grouped_events: list[tuple[str, list[EventPost]]]
