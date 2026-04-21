# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Marketplace Missions MVP v0.

A `MissionOffer` is a pige / freelance job posted by an editor (publisher,
agency...) looking for an author. A `MissionApplication` is a journalist's
candidacy on such an offer.

See `local-notes/plans/marketplace-mvp.md` for the full plan.
"""

from __future__ import annotations

from datetime import datetime

import sqlalchemy as sa
from aenum import StrEnum, auto
from sqlalchemy import BigInteger, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.models.content.mixins import ClassificationMixin, Publishable
from app.models.mixins import IdMixin, LifeCycleMixin, Owned

from ._products import MarketplaceContent

__all__ = [
    "ApplicationStatus",
    "MissionApplication",
    "MissionOffer",
    "MissionStatus",
]


class MissionStatus(StrEnum):
    """Extra lifecycle states specific to missions.

    Reuses `PublicationStatus` where possible, but adds FILLED — the
    mission is still visible but no more applications are accepted.
    """

    OPEN = auto()
    FILLED = auto()
    CLOSED = auto()


class ApplicationStatus(StrEnum):
    PENDING = auto()
    SELECTED = auto()
    REJECTED = auto()


class MissionOffer(MarketplaceContent, ClassificationMixin, Publishable):
    __tablename__ = "mkp_mission_offer"

    id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey(MarketplaceContent.id), primary_key=True
    )
    title: Mapped[str] = mapped_column(default="")
    description: Mapped[str] = mapped_column(default="")  # HTML (Trix)
    location: Mapped[str] = mapped_column(default="")
    budget_min: Mapped[int | None] = mapped_column(default=None)  # cents
    budget_max: Mapped[int | None] = mapped_column(default=None)  # cents
    currency: Mapped[str] = mapped_column(default="EUR")
    deadline: Mapped[datetime | None] = mapped_column(
        sa.DateTime(timezone=True), default=None
    )
    contact_email: Mapped[str] = mapped_column(default="")
    emitter_org_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("crp_organisation.id"), default=None
    )
    mission_status: Mapped[MissionStatus] = mapped_column(
        default=MissionStatus.OPEN
    )

    emitter_org = relationship(
        "Organisation", foreign_keys=[emitter_org_id]
    )
    applications = relationship(
        "MissionApplication",
        back_populates="mission",
        cascade="all, delete-orphan",
    )


class MissionApplication(IdMixin, LifeCycleMixin, Owned, Base):
    __tablename__ = "mkp_mission_application"
    __table_args__ = (
        UniqueConstraint(
            "mission_id", "owner_id", name="uq_mkp_mission_application_user"
        ),
    )

    mission_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("mkp_mission_offer.id", ondelete="CASCADE")
    )
    message: Mapped[str] = mapped_column(default="")
    status: Mapped[ApplicationStatus] = mapped_column(
        default=ApplicationStatus.PENDING
    )

    mission = relationship(MissionOffer, back_populates="applications")
