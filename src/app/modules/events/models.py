# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from typing import ClassVar

import sqlalchemy as sa
from sqlalchemy import (
    BigInteger,
)
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func
from sqlalchemy_utils import ArrowType
from sqlalchemy_utils.functions.orm import hybrid_property

from app.models.auth import User
from app.models.base import Base
from app.models.content.base import BaseContent
from app.models.content.mixins import Publishable, Searchable
from app.models.mixins import Addressable, UserFeedbackMixin

"""
'-----------------------------------------------------------------
'Event package
'-----------------------------------------------------------------

abstract class Event {
    +name: string
    +note: string
    +start_datetime: DateTime
    +end_datetime: DateTime
    +location: Location
}
Event -up-|> BaseContent

"""


class EventPostBase(
    BaseContent, UserFeedbackMixin, Publishable, Searchable, Addressable
):
    """
    Based in part on:
    - https://microformats.org/wiki/h-event
    """

    # Inherited from BaseContent
    # - summary: short summary of the event (plain text)
    # - content: more detailed description of the event (html)

    # Event schedule (full datetime with timezone)
    start_datetime: Mapped[ArrowType | None] = mapped_column(
        ArrowType(timezone=True), info={"group": "dates"}
    )
    end_datetime: Mapped[ArrowType | None] = mapped_column(
        ArrowType(timezone=True), info={"group": "dates"}
    )

    # Classification
    # "genre" is "event_type"
    genre: Mapped[str] = mapped_column(default="", info={"group": "metadata"})
    sector: Mapped[str] = mapped_column(default="", info={"group": "metadata"})
    # First part of the enven_type
    # ie:   event_type = "Business / Forum
    #       category = "business"
    category: Mapped[str] = mapped_column(default="", info={"group": "metadata"})
    language: Mapped[str] = mapped_column(default="FRE", info={"group": "metadata"})

    logo_url: Mapped[str] = mapped_column(default="")
    cover_image_url: Mapped[str] = mapped_column(default="")

    # only for compatibility with BaseContent:
    location: Mapped[str] = mapped_column(default="", info={"group": "location"})

    class Meta:
        groups: ClassVar[dict] = {
            "dates": ["start_datetime", "end_datetime"],
            "metadata": ["genre", "category", "language", "sector"],
        }

    # Also:
    # attendees
    # organizers


class EventPost(EventPostBase):
    __tablename__ = "evt_event_post"

    id: Mapped[int] = mapped_column(
        sa.BigInteger, sa.ForeignKey(BaseContent.id), primary_key=True
    )

    # id of the corresponding eventroom event (if any)
    eventroom_id: Mapped[int | None] = mapped_column(
        BigInteger, index=True, nullable=True
    )
    # Note: `address` is inherited from Addressable mixin via EventPostBase
    pays_zip_ville: Mapped[str] = mapped_column(default="")
    pays_zip_ville_detail: Mapped[str] = mapped_column(default="")

    @hybrid_property
    def code_postal(self) -> str:
        """Return the zip code"""
        if not self.pays_zip_ville_detail:
            return ""
        try:
            return self.pays_zip_ville_detail.split()[2]
        except IndexError:
            return ""

    @code_postal.expression
    def code_postal(cls):
        """SQL expression for the zip code property."""
        return func.coalesce(func.split_part(cls.pays_zip_ville_detail, " ", 3))

    @hybrid_property
    def departement(self) -> str:
        """Return the 2 first digit of zip code"""
        if not self.pays_zip_ville_detail:
            return ""
        try:
            return self.pays_zip_ville_detail.split()[2][:2]
        except IndexError:
            return ""

    @departement.expression
    def departement(cls):
        """SQL expression for the departement property."""
        return func.coalesce(
            func.substring(func.split_part(cls.pays_zip_ville_detail, " ", 3), 1, 2),
            "",
        )

    @hybrid_property
    def ville(self) -> str:
        """Return the 4th part of pays_zip_ville_detail"""
        if not self.pays_zip_ville_detail:
            return ""
        try:
            data = self.pays_zip_ville_detail.split()[3]
            if data.endswith('"}'):  # fixme: origin of bad formatting in test data?
                return data[:-2]
            return data
        except IndexError:
            return ""

    @ville.expression
    def ville(cls):
        """SQL expression for the ville property."""
        part = func.split_part(cls.pays_zip_ville_detail, " ", 4)
        return func.coalesce(func.rtrim(part, '"}'), "")


class PublicEvent(EventPostBase):
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
        type_label = "Salon/Colloque"


class PressEvent(EventPostBase):
    __tablename__ = "evt_press_event"

    id: Mapped[int] = mapped_column(
        sa.BigInteger, sa.ForeignKey(BaseContent.id), primary_key=True
    )

    # id = sa.Column(sa.Integer, sa.ForeignKey(BaseContent.id), primary_key=True)
    # +subtype: <PressConference, PressBriefing, PressMeal>

    class Meta:
        type_id = "press"
        type_label = "Presse"


class TrainingEvent(EventPostBase):
    __tablename__ = "evt_training_event"

    id: Mapped[int] = mapped_column(
        sa.BigInteger, sa.ForeignKey(BaseContent.id), primary_key=True
    )

    class Meta:
        type_id = "webinar"
        type_label = "Webinar"


class CultureEvent(EventPostBase):
    __tablename__ = "evt_culture_event"

    id: Mapped[int] = mapped_column(
        sa.BigInteger, sa.ForeignKey(BaseContent.id), primary_key=True
    )

    class Meta:
        type_id = "culture"
        type_label = "Événement culturel"


class ContestEvent(EventPostBase):
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


participation_table = sa.Table(
    "evt_participation",
    Base.metadata,
    sa.Column(
        "user_id",
        sa.Integer,
        sa.ForeignKey(User.id, onupdate="CASCADE", ondelete="CASCADE"),
    ),
    sa.Column(
        "event_id",
        sa.BigInteger,
        sa.ForeignKey(EventPost.id, onupdate="CASCADE", ondelete="CASCADE"),
    ),
    sa.UniqueConstraint("user_id", "event_id"),
)
