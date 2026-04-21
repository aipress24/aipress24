# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Log of notifications sent to experts for Avis d'Enquête (anti-spam).

One row per `(user_id, avis_enquete_id)` each time a notification is
actually sent. Queried by the anti-spam filter to cap the number of
notifications an expert can receive per rolling 30-day window.
"""

from __future__ import annotations

from datetime import UTC, datetime

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.models.mixins import IdMixin


class AvisNotificationLog(IdMixin, Base):
    __tablename__ = "nrm_avis_notification_log"

    user_id: Mapped[int] = mapped_column(
        sa.ForeignKey("aut_user.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    avis_enquete_id: Mapped[int | None] = mapped_column(
        sa.ForeignKey("nrm_avis_enquete.id", ondelete="SET NULL"),
        nullable=True,
    )
    sent_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
        index=True,
    )
