# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from typing import cast

from arrow import Arrow
from attr import define

from app.flask.lib.pywire import Component, component
from app.flask.lib.view_model import ViewModel
from app.models.meta import get_meta_attr
from app.modules.bw.bw_activation.user_utils import get_organisation_logo_url
from app.modules.events.components.opening_hours import opening_hours
from app.modules.events.models import EventPost

DEFAULT_LOGO_URL = "/static/img/transparent-square.png"


@define
class EventCardVM(ViewModel):
    """View model for event card component."""

    def extra_attrs(self) -> dict:
        event = cast("EventPost", self._model)

        # Compute opening hours only if both dates are set
        if event.start_datetime and event.end_datetime:
            start = cast(Arrow, event.start_datetime)
            end = cast(Arrow, event.end_datetime)
            opening = opening_hours(start, end)
        else:
            opening = ""

        return {
            "author": event.owner,
            "organisation_image_url": self._get_organisation_logo_url(),
            "type_id": get_meta_attr(event, "type_id", ""),
            "type_label": get_meta_attr(event, "type_label", ""),
            "opening": opening,
            "likes": event.like_count,
            "replies": event.comment_count,
            "views": event.view_count,
        }

    def _get_organisation_logo_url(self) -> str:
        """Get the organisation logo URL from the event owner."""

        event = cast("EventPost", self._model)
        owner = event.owner
        if owner and owner.organisation:
            return get_organisation_logo_url(owner.organisation)
        return DEFAULT_LOGO_URL


@component
@define
class EventCard(Component):
    event: EventPost
    # Accepted for parity with `PostCard`: the org / member tab
    # includes call every card the same way —
    # `component("…-card", obj, class_="bg-gray-100")`. Without this
    # field the events tab 500s with « unexpected keyword argument
    # 'class_' » (prod fe36ebd9). Kept optional so the bare
    # positional call still works.
    class_: str = ""

    def __attrs_post_init__(self) -> None:
        # Wrap event in ViewModel for clean computed property access
        self.event = EventCardVM(self.event)
