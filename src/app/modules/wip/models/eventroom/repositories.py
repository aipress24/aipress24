# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from advanced_alchemy.repository import SQLAlchemySyncRepository
from flask_super.decorators import service

from app.services.repositories import OwnedRepository

from .event import Event, EventImage


#
# Commroom models
#
@service
class EventRepository(OwnedRepository[Event]):
    # OwnedRepository adds list_owned/get_owned (used by the public API's
    # /me/events tier) on top of the base Repository; all other behaviour is
    # unchanged. Event is Owned + LifeCycleMixin, so owner-scoping is valid.
    model_type = Event


class EventImageRepository(SQLAlchemySyncRepository[EventImage]):
    """Repository for EventImage model."""

    model_type = EventImage
