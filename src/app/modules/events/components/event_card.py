# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from typing import cast

from attr import define

from app.flask.lib.pywire import Component, component
from app.flask.lib.view_model import ViewModel
from app.models.meta import get_meta_attr
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
            opening = opening_hours(event.start_datetime, event.end_datetime)
        else:
            opening = ""

        return {
            "author": event.owner,
            "organisation_image_url": self._get_organisation_logo_url(event),
            "type_id": get_meta_attr(event, "type_id", ""),
            "type_label": get_meta_attr(event, "type_label", ""),
            "opening": opening,
            "likes": event.like_count,
            "replies": event.comment_count,
            "views": event.view_count,
        }

    @staticmethod
    def _get_organisation_logo_url(event: EventPost) -> str:
        """Get the organisation logo URL from the event owner."""
        owner = event.owner
        if owner and owner.organisation:
            return owner.organisation.logo_image_signed_url()
        return DEFAULT_LOGO_URL


@component
@define
class EventCard(Component):
    event: EventPost

    def __attrs_post_init__(self) -> None:
        # Wrap event in ViewModel for clean computed property access
        self.event = EventCardVM(self.event)  # type: ignore[assignment]
