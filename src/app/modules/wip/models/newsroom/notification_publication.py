# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Notification de publication — signal envoyé aux participants d'un article.

Deux modes d'émission :
- **A** depuis un avis d'enquête existant : le journaliste notifie les
  experts qu'il avait contactés (typiquement ceux qui avaient accepté).
- **B** en saisie libre : le journaliste cible des membres d'AiPRESS24
  cités dans l'article sans être passés par un avis d'enquête.

À ne pas confondre avec le « justificatif de publication » (produit
commercial vendu sur `/wire/<id>/buy/justificatif`, MVP W17 paywall).

Spec: `local-notes/specs/notification-publication.md`.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

import arrow
import sqlalchemy as sa
from sqlalchemy import orm
from sqlalchemy.orm import Mapped, mapped_column

from app.models.auth import User
from app.models.base import Base
from app.models.mixins import IdMixin, Owned

if TYPE_CHECKING:
    from .article import Article
    from .avis_enquete import AvisEnquete, ContactAvisEnquete


class NotificationPublication(IdMixin, Owned, Base):
    """Notification de publication envoyée par un journaliste.

    Créée au moment où le journaliste clique « Envoyer ». Pas de
    lifecycle : les emails et notifications in-app partent en
    fire-and-forget à la création.
    """

    __tablename__ = "nrm_notification_publication"

    # Avis d'enquête d'origine (mode A). Null = mode B (saisie libre).
    avis_enquete_id: Mapped[int | None] = mapped_column(
        sa.ForeignKey("nrm_avis_enquete.id", ondelete="SET NULL"),
        nullable=True,
    )
    avis_enquete: Mapped[AvisEnquete | None] = orm.relationship(
        "AvisEnquete", foreign_keys=[avis_enquete_id]
    )

    # Article interne si connu et publié sur AiPRESS24, sinon null
    # (cas : republication externe, citation sur site tiers, etc.).
    article_id: Mapped[int | None] = mapped_column(
        sa.ForeignKey("nrm_article.id", ondelete="SET NULL"),
        nullable=True,
    )
    article: Mapped[Article | None] = orm.relationship(
        "Article", foreign_keys=[article_id]
    )

    # Lien canonique vers l'article (toujours rempli, interne ou externe).
    article_url: Mapped[str] = mapped_column(sa.String, default="")
    # Titre de l'article (snapshot au moment de l'envoi).
    article_title: Mapped[str] = mapped_column(sa.String, default="")
    # Message libre du journaliste (optionnel).
    message: Mapped[str] = mapped_column(sa.Text, default="")

    notified_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        default=lambda: arrow.now("Europe/Paris").datetime,
        nullable=False,
    )

    contacts: Mapped[list[NotificationPublicationContact]] = orm.relationship(
        "NotificationPublicationContact",
        back_populates="notification",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        sa.Index("ix_nrm_notification_publication_article_url", "article_url"),
    )


class NotificationPublicationContact(IdMixin, Base):
    """Un destinataire d'une notification de publication."""

    __tablename__ = "nrm_notification_publication_contact"

    notification_id: Mapped[int] = mapped_column(
        sa.ForeignKey("nrm_notification_publication.id", ondelete="CASCADE"),
        nullable=False,
    )
    notification: Mapped[NotificationPublication] = orm.relationship(
        "NotificationPublication",
        foreign_keys=[notification_id],
        back_populates="contacts",
    )

    # Destinataire direct (user AiPRESS24).
    recipient_user_id: Mapped[int] = mapped_column(
        sa.ForeignKey(User.id, ondelete="CASCADE"),
        nullable=False,
    )
    recipient: Mapped[User] = orm.relationship(User, foreign_keys=[recipient_user_id])

    # Provenance optionnelle : contact d'avis d'enquête (mode A).
    contact_avis_enquete_id: Mapped[int | None] = mapped_column(
        sa.ForeignKey("nrm_contact_avis_enquete.id", ondelete="SET NULL"),
        nullable=True,
    )
    contact_avis_enquete: Mapped[ContactAvisEnquete | None] = orm.relationship(
        "ContactAvisEnquete", foreign_keys=[contact_avis_enquete_id]
    )

    sent_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        default=lambda: arrow.now("Europe/Paris").datetime,
        nullable=False,
    )
    read_at: Mapped[datetime | None] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=True,
    )

    __table_args__ = (
        sa.Index(
            "ix_nrm_notification_publication_contact_recipient_sent",
            "recipient_user_id",
            "sent_at",
        ),
        sa.UniqueConstraint(
            "notification_id",
            "recipient_user_id",
            name="uq_npc_notification_id_recipient_user_id",
        ),
    )
