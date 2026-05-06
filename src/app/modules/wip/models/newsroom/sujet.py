# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.models.lifecycle import PublicationStatus

from ._base import (
    CiblageMixin,
    NewsMetadataMixin,
    NewsroomCommonMixin,
)


class Sujet(
    NewsroomCommonMixin,
    NewsMetadataMixin,
    CiblageMixin,
    Base,
):
    __tablename__ = "nrm_sujet"

    # Workflow: DRAFT → PENDING (validated) → PUBLIC (published)
    # Can also be: REJECTED, ARCHIVED

    # ------------------------------------------------------------
    # Dates
    # ------------------------------------------------------------

    # Limite de validité
    date_limite_validite: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True))

    # Parution prévue
    date_parution_prevue: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True))

    status: Mapped[PublicationStatus] = mapped_column(
        sa.Enum(PublicationStatus), default=PublicationStatus.DRAFT
    )

    pays_zip_ville: Mapped[str] = mapped_column(default="")
    pays_zip_ville_detail: Mapped[str] = mapped_column(default="")

    # ------------------------------------------------------------
    # Lifecycle (bug 0132)
    # ------------------------------------------------------------

    def can_publish(self) -> bool:
        return self.status == PublicationStatus.DRAFT

    def can_unpublish(self) -> bool:
        return self.status == PublicationStatus.PUBLIC

    def publish(self) -> None:
        """Move the sujet from DRAFT to PUBLIC.

        Bug 0132: previously SujetsWipView had no publish action and the
        sujet sat as DRAFT forever, so journalists at the targeted media
        never received a proposal.
        """
        if not self.can_publish():
            msg = "Cannot publish sujet: not in DRAFT status"
            raise ValueError(msg)
        if not self.titre or not self.titre.strip():
            msg = "Cannot publish sujet: titre is required"
            raise ValueError(msg)
        if not self.contenu or not self.contenu.strip():
            msg = "Cannot publish sujet: contenu is required"
            raise ValueError(msg)
        self.status = PublicationStatus.PUBLIC  # type: ignore[assignment]

    def unpublish(self) -> None:
        if not self.can_unpublish():
            msg = "Cannot unpublish sujet: not in PUBLIC status"
            raise ValueError(msg)
        self.status = PublicationStatus.DRAFT  # type: ignore[assignment]
