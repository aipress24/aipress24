# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Marketplace Offers (Missions, Projects, Jobs).

All offer types are polymorphic sub-classes of `MarketplaceContent`;
they share the same primary-key space (`mkp_content.id`), which lets a
single generic `OfferApplication` table target any offer kind via
`offer_id → mkp_content.id`.

- `MissionOffer` (pige / freelance) — v0
- `ProjectOffer` (éditorial collectif) — v0.1
- `JobOffer` (poste permanent ou CDD) — v0.2

`OfferApplication` is the unified candidature model. A `cv_url` column
is carried for Job applications (v0.2) but stays empty for missions
and projects.
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
    "ContractType",
    "JobOffer",
    "MissionOffer",
    "MissionStatus",
    "OfferApplication",
    "ProjectOffer",
]


class MissionStatus(StrEnum):
    """Shared lifecycle for offer types (missions, projects, jobs).

    Kept under the historical name `MissionStatus` since the DB enum
    is already named `missionstatus`; reused for projects and jobs.
    """

    OPEN = auto()
    FILLED = auto()
    CLOSED = auto()


class ApplicationStatus(StrEnum):
    PENDING = auto()
    SELECTED = auto()
    REJECTED = auto()


class ContractType(StrEnum):
    CDI = "CDI"
    CDD = "CDD"
    STAGE = "STAGE"
    APPRENTISSAGE = "APPRENTISSAGE"
    FREELANCE = "FREELANCE"


class MissionOffer(MarketplaceContent, ClassificationMixin, Publishable):
    __tablename__ = "mkp_mission_offer"

    id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey(MarketplaceContent.id), primary_key=True
    )
    title: Mapped[str] = mapped_column(default="")
    description: Mapped[str] = mapped_column(default="")
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
    mission_status: Mapped[MissionStatus] = mapped_column(default=MissionStatus.OPEN)

    emitter_org = relationship("Organisation", foreign_keys=[emitter_org_id])


class ProjectOffer(MarketplaceContent, ClassificationMixin, Publishable):
    """Editorial project — bigger than a pige (dossier, série, enquête)."""

    __tablename__ = "mkp_project_offer"

    id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey(MarketplaceContent.id), primary_key=True
    )
    title: Mapped[str] = mapped_column(default="")
    description: Mapped[str] = mapped_column(default="")
    location: Mapped[str] = mapped_column(default="")
    budget_min: Mapped[int | None] = mapped_column(default=None)
    budget_max: Mapped[int | None] = mapped_column(default=None)
    currency: Mapped[str] = mapped_column(default="EUR")
    deadline: Mapped[datetime | None] = mapped_column(
        sa.DateTime(timezone=True), default=None
    )
    contact_email: Mapped[str] = mapped_column(default="")
    emitter_org_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("crp_organisation.id"), default=None
    )
    mission_status: Mapped[MissionStatus] = mapped_column(default=MissionStatus.OPEN)
    team_size: Mapped[int | None] = mapped_column(default=None)
    duration_months: Mapped[int | None] = mapped_column(default=None)
    project_type: Mapped[str] = mapped_column(default="")

    emitter_org = relationship("Organisation", foreign_keys=[emitter_org_id])


class JobOffer(MarketplaceContent, ClassificationMixin, Publishable):
    """Salaried or fixed-term position at a media / agency / org."""

    __tablename__ = "mkp_job_offer"

    id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey(MarketplaceContent.id), primary_key=True
    )
    title: Mapped[str] = mapped_column(default="")
    description: Mapped[str] = mapped_column(default="")
    location: Mapped[str] = mapped_column(default="")
    salary_min: Mapped[int | None] = mapped_column(default=None)  # cents/year
    salary_max: Mapped[int | None] = mapped_column(default=None)
    currency: Mapped[str] = mapped_column(default="EUR")
    starting_date: Mapped[datetime | None] = mapped_column(
        sa.DateTime(timezone=True), default=None
    )
    contact_email: Mapped[str] = mapped_column(default="")
    emitter_org_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("crp_organisation.id"), default=None
    )
    mission_status: Mapped[MissionStatus] = mapped_column(default=MissionStatus.OPEN)
    contract_type: Mapped[ContractType] = mapped_column(default=ContractType.CDI)
    full_time: Mapped[bool] = mapped_column(default=True)
    remote_ok: Mapped[bool] = mapped_column(default=False)

    emitter_org = relationship("Organisation", foreign_keys=[emitter_org_id])


class OfferApplication(IdMixin, LifeCycleMixin, Owned, Base):
    """Candidacy to any Offer type (mission, project, job).

    `offer_id` targets `mkp_content.id` directly — all offer kinds live
    in that ID space. The optional `cv_url` is populated only for job
    applications in v0; proper S3 upload is deferred to v0.2.x.
    """

    __tablename__ = "mkp_offer_application"
    __table_args__ = (
        UniqueConstraint("offer_id", "owner_id", name="uq_mkp_offer_application_user"),
    )

    offer_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("mkp_content.id", ondelete="CASCADE"),
    )
    message: Mapped[str] = mapped_column(default="")
    cv_url: Mapped[str] = mapped_column(default="")
    status: Mapped[ApplicationStatus] = mapped_column(default=ApplicationStatus.PENDING)
