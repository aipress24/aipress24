# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base

from ._base import NewsMetadataMixin, NewsroomCommonMixin, StatutMixin


class JustifPublication(
    NewsroomCommonMixin,
    NewsMetadataMixin,
    StatutMixin,
    Base,
):
    __tablename__ = "nrm_justif_publication"

    # ------------------------------------------------------------
    # Dates
    # ------------------------------------------------------------

    # Parution prévue
    date_parution_prevue: Mapped[datetime] = mapped_column(sa.DateTime)

    # Publié sur AIP24
    date_publication_aip24: Mapped[datetime] = mapped_column(sa.DateTime)
