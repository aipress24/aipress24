# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.models.lifecycle import PublicationStatus

if TYPE_CHECKING:
    from app.models.auth import User

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

    def can_edit(self) -> bool:
        return self.status != PublicationStatus.ARCHIVED

    def can_publish(self) -> bool:
        return self.status == PublicationStatus.DRAFT

    def can_delete(self, user: User | None = None) -> bool:
        if user is not None:
            user_id = getattr(user, "id", None)
            if user_id is not None and user_id != self.owner_id:
                return False
        return True

    def can_unpublish(self, user: User | None = None) -> bool:
        if self.status != PublicationStatus.PUBLIC:
            return False
        if user is not None:
            user_id = getattr(user, "id", None)
            if user_id is not None and user_id != self.owner_id:
                return False
        return True

    def publish(self) -> None:
        """Move the sujet from DRAFT to PUBLIC.

        Bug 0132: previously SujetsWipView had no publish action and the
        sujet sat as DRAFT forever, so journalists at the targeted media
        never received a proposal.
        """
        if not self.can_publish():
            msg = "Impossible de publier: le sujet n'a pas le statut DRAFT"
            raise ValueError(msg)
        if not self.titre or not self.titre.strip():
            msg = "Impossible de publier: le sujet n'a pas de titre"
            raise ValueError(msg)
        if not self.contenu or not self.contenu.strip():
            msg = "Impossible de publier: le sujet n'a pas de contenu"
            raise ValueError(msg)
        self.status = PublicationStatus.PUBLIC  # type: ignore[assignment]

    def unpublish(self, user: User | None = None) -> None:
        if not self.can_unpublish(user):
            if self.status != PublicationStatus.PUBLIC:
                msg = "Impossible de dépublier: le sujet n'est pas PUBLIC"
            else:
                msg = "Impossible de dépublier: seul le créateur du sujet peut le dépublier"
            raise ValueError(msg)
        self.status = PublicationStatus.DRAFT  # type: ignore[assignment]
