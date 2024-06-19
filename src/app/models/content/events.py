# Copyright (c) 2021-2024 - Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""
'-----------------------------------------------------------------
'Event package
'-----------------------------------------------------------------

abstract class Event {
    +name: string
    +note: string
    +start_date: DateTime
    +end_date: DateTime
    +location: Location
}
Event -up-|> BaseContent

"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy_utils import ArrowType

from ..mixins import Addressable, UserFeedbackMixin
from .base import BaseContent
from .mixins import Publishable, Searchable


class Event(BaseContent, UserFeedbackMixin, Publishable, Searchable, Addressable):
    """
    Based in part on:
    - https://microformats.org/wiki/h-event
    """

    # Inherited from BaseContent
    # - summary: short summary of the event (plain text)
    # - content: more detailed description of the event (html)

    #: where the event takes place
    location: Mapped[str] = mapped_column(default="", info={"group": "location"})

    # Or use datetimes?
    start_date: Mapped[ArrowType | None] = mapped_column(
        ArrowType, info={"group": "dates"}
    )
    end_date: Mapped[ArrowType | None] = mapped_column(
        ArrowType, info={"group": "dates"}
    )

    # FIXME
    start_time: Mapped[ArrowType | None] = mapped_column(
        ArrowType, info={"group": "dates"}
    )
    end_time: Mapped[ArrowType | None] = mapped_column(
        ArrowType, info={"group": "dates"}
    )

    # Classification
    genre: Mapped[str] = mapped_column(default="", info={"group": "metadata"})
    sector: Mapped[str] = mapped_column(default="", info={"group": "metadata"})
    category: Mapped[str] = mapped_column(default="", info={"group": "metadata"})
    language: Mapped[str] = mapped_column(default="FRE", info={"group": "metadata"})

    logo_url: Mapped[str] = mapped_column(default="")
    cover_image_url: Mapped[str] = mapped_column(default="")

    class Meta:
        groups = {
            "dates": ["start_date", "end_date", "start_time", "end_time"],
            "metadata": ["genre", "category", "language", "sector"],
        }

    # Also:
    # attendees
    # organizers


class PublicEvent(Event):
    __tablename__ = "evt_public_event"

    id: Mapped[int] = mapped_column(
        sa.BigInteger, sa.ForeignKey(BaseContent.id), primary_key=True
    )

    # +subtype: <Webinar, TradeShow, Symposium, Demonstration, FlashMob, Meetup...>

    # +sector: [choices TBD]
    # +audience: [choices TBD]
    # +is_paying: bool
    # +is_online: bool
    # +is_irl: bool

    class Meta:
        type_id = "public"
        type_label = "Salons/Colloques"


class PressEvent(Event):
    __tablename__ = "evt_press_event"

    id: Mapped[int] = mapped_column(
        sa.BigInteger, sa.ForeignKey(BaseContent.id), primary_key=True
    )

    # id = sa.Column(sa.Integer, sa.ForeignKey(BaseContent.id), primary_key=True)
    # +subtype: <PressConference, PressBriefing, PressMeal>

    class Meta:
        type_id = "press"
        type_label = "Presse"


class TrainingEvent(Event):
    __tablename__ = "evt_training_event"

    id: Mapped[int] = mapped_column(
        sa.BigInteger, sa.ForeignKey(BaseContent.id), primary_key=True
    )

    class Meta:
        type_id = "webinar"
        type_label = "Webinar"


class CultureEvent(Event):
    __tablename__ = "evt_culture_event"

    id: Mapped[int] = mapped_column(
        sa.BigInteger, sa.ForeignKey(BaseContent.id), primary_key=True
    )

    class Meta:
        type_id = "culture"
        type_label = "Événement culturel"


class ContestEvent(Event):
    __tablename__ = "evt_contest_event"

    id: Mapped[int] = mapped_column(
        sa.BigInteger, sa.ForeignKey(BaseContent.id), primary_key=True
    )

    class Meta:
        type_id = "contest"
        type_label = "Concours"


EVENT_CLASSES = [
    PublicEvent,
    PressEvent,
    TrainingEvent,
    CultureEvent,
    ContestEvent,
]
