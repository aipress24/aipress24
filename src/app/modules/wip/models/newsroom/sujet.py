# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.modules.wip.models.newsroom._base import (
    CiblageMixin,
    NewsMetadataMixin,
    NewsroomCommonMixin,
    StatutMixin,
)


class Sujet(
    NewsroomCommonMixin,
    NewsMetadataMixin,
    CiblageMixin,
    StatutMixin,
    Base,
):
    __tablename__ = "nrm_sujet"

    # Etat: Accepté, Refusé, En discussion, Annulé
    # Etat: Brouillon, Validé, Publié

    # ------------------------------------------------------------
    # Dates
    # ------------------------------------------------------------

    # Limite de validité
    date_limite_validite: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True))

    # Parution prévue
    date_parution_prevue: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True))
