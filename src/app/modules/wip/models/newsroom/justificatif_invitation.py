# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Ticket #0195 — per-recipient record of a Justificatif de publication
invitation. Created in `notify_avis_participants_of_justificatif` for
each (article, recipient) pair, alongside the bell notification.

Replaces the fragile `Notification.message.like('%a publié un article…')`
reverse-engineering in `_render_justificatifs_tab`.

One row per (article, recipient) — a journalist can notify the same
person about different articles, or different people about the same
article. The (article_id, recipient_id) pair is therefore not unique
(separate invites for different enquêtes on the same article are
possible).
"""

from __future__ import annotations

from sqlalchemy import BigInteger, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.models.mixins import IdMixin, Timestamped


class JustificatifInvitation(IdMixin, Timestamped, Base):
    __tablename__ = "nrm_justificatif_invitation"

    article_id: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        index=True,
        comment="FK to nrm_article.id or frt_content.id (loose ref — no DB constraint)",
    )
    recipient_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("aut_user.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    journalist_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("aut_user.id", ondelete="CASCADE"),
        nullable=False,
    )
    avis_enquete_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("nrm_avis_enquete.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
