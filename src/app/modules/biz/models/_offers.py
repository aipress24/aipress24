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
from enum import StrEnum, auto

import sqlalchemy as sa
from sqlalchemy import JSON, BigInteger, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from sqlalchemy_utils.functions.orm import hybrid_property

from app.models.base import Base
from app.models.content.mixins import ClassificationMixin, Publishable
from app.models.mixins import IdMixin, LifeCycleMixin, Owned

from ._products import MarketplaceContent

__all__ = [
    "ApplicationStatus",
    "ContractType",
    "JobOffer",
    "MissionCategory",
    "MissionOffer",
    "MissionStatus",
    "OfferApplication",
    "ProjectOffer",
]


class MissionCategory(StrEnum):
    """Bug #0185 (Erick, 2026-06-04) : top-level sub-typing of
    marketplace Missions :

    > 1- Pour le journalisme (annonces visibles seulement par les
    >    journalistes)
    > 2- Pour la Communication (les PR Agencies et les PR Indeps)
    > 3- Pour l'innovation dans le journalisme et la communication.

    `.value` is the lowercase enum name (« journalisme » /
    « communication » / « innovation »), kept as the wire format on
    the form, in URLs, and in the DB row.
    """

    JOURNALISME = auto()
    COMMUNICATION = auto()
    INNOVATION = auto()


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
    DOCTORAL = "DOCTORAL"


class MissionOffer(MarketplaceContent, ClassificationMixin, Publishable):
    __tablename__ = "mkp_mission_offer"

    id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey(MarketplaceContent.id), primary_key=True
    )
    title: Mapped[str] = mapped_column(default="")
    description: Mapped[str] = mapped_column(default="")
    location: Mapped[str] = mapped_column(default="")
    pays_zip_ville: Mapped[str] = mapped_column(default="")
    pays_zip_ville_detail: Mapped[str] = mapped_column(default="")
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
    # Bug #0185 — top-level category + free-text sub-category
    # (placeholder until Erick's `type_mission_*` ontology lands).
    # `category` stays nullable for back-compat with already-published
    # missions ; new ones surface a required selector in the form.
    category: Mapped[MissionCategory | None] = mapped_column(default=None)
    subcategory: Mapped[str] = mapped_column(default="")
    # Bug #0187 — Journalism-mission extension : 8 taxonomy lists +
    # 2 work-mode flags. The columns are present on every Mission but
    # the deposit form only exposes them when category == JOURNALISME
    # (Alpine.js gating). Default to empty list / False so old code
    # paths and back-compat rows stay valid.
    metiers_journalisme: Mapped[list] = mapped_column(JSON, default=list)
    types_entreprises_presse_medias: Mapped[list] = mapped_column(JSON, default=list)
    types_presse_medias: Mapped[list] = mapped_column(JSON, default=list)
    competences_journalisme: Mapped[list] = mapped_column(JSON, default=list)
    langues: Mapped[list] = mapped_column(JSON, default=list)
    types_contenus_editoriaux: Mapped[list] = mapped_column(JSON, default=list)
    taille_contenus_editoriaux: Mapped[list] = mapped_column(JSON, default=list)
    modes_remuneration: Mapped[list] = mapped_column(JSON, default=list)
    physical_required: Mapped[bool] = mapped_column(default=False)
    remote_required: Mapped[bool] = mapped_column(default=False)

    @hybrid_property
    def code_postal(self) -> str:
        """Return the zip code."""
        if not self.pays_zip_ville_detail:
            return ""
        try:
            return self.pays_zip_ville_detail.split()[2]
        except IndexError:
            return ""

    @code_postal.expression
    def code_postal(cls):
        """SQL expression for the zip code property."""
        return func.coalesce(func.split_part(cls.pays_zip_ville_detail, " ", 3), "")

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
        """Return the city from `pays_zip_ville_detail`.

        return the 4th part of pays_zip_ville_detail."""
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

    @hybrid_property
    def type_mission(self) -> str:
        """Return the category value (type of mission)."""
        if self.category is None:
            return ""
        return (
            self.category.value
            if isinstance(self.category, StrEnum)
            else str(self.category)
        )

    @type_mission.expression
    def type_mission(cls):
        """SQL expression for the type_mission property."""
        return cls.category

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
    pays_zip_ville: Mapped[str] = mapped_column(default="")
    pays_zip_ville_detail: Mapped[str] = mapped_column(default="")
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
    # Ticket #0198 — top-level category (« journalisme » / « communication »
    # / « innovation » as in the `type_projets` taxonomy) + sub-type
    # drawn from the matching per-category taxonomy
    # (`type_projet_journalisme` etc.).
    project_category: Mapped[str] = mapped_column(default="")
    project_type: Mapped[str] = mapped_column(default="")

    @hybrid_property
    def code_postal(self) -> str:
        """Return the zip code."""
        if not self.pays_zip_ville_detail:
            return ""
        try:
            return self.pays_zip_ville_detail.split()[2]
        except IndexError:
            return ""

    @code_postal.expression
    def code_postal(cls):
        """SQL expression for the zip code property."""
        return func.coalesce(func.split_part(cls.pays_zip_ville_detail, " ", 3), "")

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
        """Return the city from `pays_zip_ville_detail`.

        return the 4th part of pays_zip_ville_detail."""
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

    emitter_org = relationship("Organisation", foreign_keys=[emitter_org_id])


class JobOffer(MarketplaceContent, ClassificationMixin, Publishable):
    """Salaried or fixed-term position at a media / agency / org."""

    __tablename__ = "mkp_job_offer"

    id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey(MarketplaceContent.id), primary_key=True
    )
    title: Mapped[str] = mapped_column(default="")
    description: Mapped[str] = mapped_column(default="")
    statut: Mapped[str] = mapped_column(default="")  # Etudiant / pro
    domain_studient: Mapped[list] = mapped_column(
        JSON, default=list
    )  # Journalisme, Communication, Innovation , type_job_studient_app
    domain_pro: Mapped[list] = mapped_column(
        JSON, default=list
    )  # Journalisme, Communication, Innovation , pour les pros: type_job_pro_app

    type_emploi_pro_studient: Mapped[list] = mapped_column(
        JSON, default=list
    )  # type_job_studient, pour etudiants

    type_emploi_pro_journaliste: Mapped[list] = mapped_column(
        JSON, default=list
    )  # journalisme_fonction, pour pro journalist
    competence_journalisme: Mapped[list] = mapped_column(
        JSON, default=list
    )  # journalisme_competence, pour pro journalist

    type_emploi_pro_communicant: Mapped[list] = mapped_column(
        JSON, default=list
    )  # press_relations_fonctions, pour pro communicant
    competence_relation_presse: Mapped[list] = mapped_column(
        JSON, default=list
    )  # press_relations_skills, pour pro communicant

    type_emploi_pro_innovation: Mapped[list] = mapped_column(
        JSON, default=list
    )  # innovation_job, pour pro innovation
    competence_innovation: Mapped[list] = mapped_column(
        JSON, default=list
    )  # innovation_skills, pour pro innovation

    niveau_etude: Mapped[list] = mapped_column(
        JSON, default=list
    )  # niveaux_etudes, pour tous
    matiere_etudiee: Mapped[list] = mapped_column(
        JSON, default=list
    )  # matieres_etudiees, pour etudiants

    location: Mapped[str] = mapped_column(default="")
    pays_zip_ville: Mapped[str] = mapped_column(default="")
    pays_zip_ville_detail: Mapped[str] = mapped_column(default="")
    langues: Mapped[list] = mapped_column(JSON, default=list)
    salary_min: Mapped[int | None] = mapped_column(default=None)  # cents/year
    salary_max: Mapped[int | None] = mapped_column(default=None)  # cents/year
    currency: Mapped[str] = mapped_column(default="EUR")
    starting_date: Mapped[datetime | None] = mapped_column(
        sa.DateTime(timezone=True), default=None
    )
    ending_date: Mapped[datetime | None] = mapped_column(
        sa.DateTime(timezone=True), default=None
    )
    contact_email: Mapped[str] = mapped_column(default="")
    emitter_org_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("crp_organisation.id"), default=None
    )
    mission_status: Mapped[MissionStatus] = mapped_column(default=MissionStatus.OPEN)
    contract_type: Mapped[ContractType] = mapped_column(default=ContractType.CDI)
    full_time: Mapped[bool] = mapped_column(default=True)  # pour tous
    partial_time: Mapped[int | None] = mapped_column(default=None)  # percent, pour tous
    remote_ok: Mapped[bool] = mapped_column(default=False)  # pour etudiants
    remote_partial_time: Mapped[bool] = mapped_column(default=False)  # pour pros
    remote_full_time: Mapped[bool] = mapped_column(default=False)  # pour pros

    @hybrid_property
    def code_postal(self) -> str:
        """Return the zip code."""
        if not self.pays_zip_ville_detail:
            return ""
        try:
            return self.pays_zip_ville_detail.split()[2]
        except IndexError:
            return ""

    @code_postal.expression
    def code_postal(cls):
        """SQL expression for the zip code property."""
        return func.coalesce(func.split_part(cls.pays_zip_ville_detail, " ", 3), "")

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
        """Return the city from `pays_zip_ville_detail`.

        return the 4th part of pays_zip_ville_detail."""
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
    # Free-text message the emitter attaches when accepting / rejecting
    # (tickets #0199 + #0200). Empty for PENDING applications.
    decision_message: Mapped[str] = mapped_column(default="")
