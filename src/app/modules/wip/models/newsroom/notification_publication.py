# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Notification de Publication - Alerte envoyée aux participants d'une enquête.

Cette fonctionnalité permet au journaliste de notifier les personnes ayant
participé à son enquête que l'article a été publié.

Note: Ne pas confondre avec le "Justificatif de Publication" qui est un
produit commercial du module BIZ (Marketplace).
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

import arrow
import sqlalchemy as sa
from sqlalchemy import orm
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.models.mixins import IdMixin, Owned

if TYPE_CHECKING:
    from .article import Article
    from .avis_enquete import AvisEnquete, ContactAvisEnquete


class NotificationPublication(IdMixin, Owned, Base):
    """Notification de publication envoyée aux participants d'une enquête.

    Créée au moment où le journaliste clique "Envoyer". Pas de lifecycle.
    Les emails et notifications in-app sont envoyés en fire-and-forget.
    """

    __tablename__ = "nrm_notification_publication"

    # Avis d'enquête concerné
    avis_enquete_id: Mapped[int] = mapped_column(
        sa.ForeignKey("nrm_avis_enquete.id", ondelete="CASCADE"),
        nullable=False,
    )
    avis_enquete: Mapped[AvisEnquete] = orm.relationship(
        "AvisEnquete", foreign_keys=[avis_enquete_id]
    )

    # Article publié
    article_id: Mapped[int] = mapped_column(
        sa.ForeignKey("nrm_article.id", ondelete="CASCADE"),
        nullable=False,
    )
    article: Mapped[Article] = orm.relationship("Article", foreign_keys=[article_id])

    # Date d'envoi (= date de création)
    notified_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        default=lambda: arrow.now("Europe/Paris").datetime,
        nullable=False,
    )

    # Contacts notifiés
    contacts: Mapped[list[NotificationPublicationContact]] = orm.relationship(
        "NotificationPublicationContact",
        back_populates="notification",
        cascade="all, delete-orphan",
    )


class NotificationPublicationContact(IdMixin, Base):
    """Contact notifié dans une notification de publication."""

    __tablename__ = "nrm_notification_publication_contact"

    # Parent notification
    notification_id: Mapped[int] = mapped_column(
        sa.ForeignKey("nrm_notification_publication.id", ondelete="CASCADE"),
        nullable=False,
    )
    notification: Mapped[NotificationPublication] = orm.relationship(
        "NotificationPublication",
        foreign_keys=[notification_id],
        back_populates="contacts",
    )

    # Contact from AvisEnquete
    contact_id: Mapped[int] = mapped_column(
        sa.ForeignKey("nrm_contact_avis_enquete.id", ondelete="CASCADE"),
        nullable=False,
    )
    contact: Mapped[ContactAvisEnquete] = orm.relationship(
        "ContactAvisEnquete", foreign_keys=[contact_id]
    )
