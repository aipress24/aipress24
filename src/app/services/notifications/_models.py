# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

import arrow
import sqlalchemy as sa
from flask_super.decorators import service
from sqlalchemy import ForeignKey, Index, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy_utils import ArrowType

from app.models.auth import User
from app.models.base import Base
from app.models.mixins import IdMixin, Timestamped
from app.services.repositories import Repository


class Notification(IdMixin, Timestamped, Base):
    __tablename__ = "not_notifications"

    receiver_id: Mapped[int] = mapped_column(
        ForeignKey(User.id, ondelete="CASCADE"), nullable=False
    )
    message: Mapped[str] = mapped_column(default="")
    url: Mapped[str] = mapped_column(default="")
    is_read: Mapped[bool] = mapped_column(default=False)

    receiver: Mapped[User] = relationship(User, foreign_keys=[receiver_id])

    # Query pattern: `WHERE receiver_id = ? AND is_read = false` (badge
    # count, per authenticated page render) and `WHERE receiver_id = ?
    # ORDER BY is_read, timestamp DESC LIMIT 10` (dropdown).
    __table_args__ = (
        Index(
            "ix_not_notifications_receiver_read_ts",
            "receiver_id",
            "is_read",
            "timestamp",
        ),
    )

    def get_abstract(self, max_length: int = 100) -> str:
        if len(self.message) < max_length:
            return self.message
        return self.message[: max_length - 3] + "..."


@service
class NotificationRepository(Repository[Notification]):
    model_type = Notification


class PendingNotification(IdMixin, Base):
    """Une notification en attente de livraison, fusionnable.

    Sert le regroupement demandé par `NOT-12` de la spécification
    EVENTS, mais ne lui appartient pas : tout module qui notifie a le
    même besoin de ne pas inonder pendant une session d'édition, et
    aucun n'a à réinventer une file d'attente pour l'obtenir.

    Une ligne par couple (destinataire, clé de regroupement). Un
    nouveau post sous la même clé **remplace** le message au lieu de
    s'y ajouter : la fenêtre livre l'état final, pas une suite d'états
    intermédiaires.

    La fenêtre est **fixe**, ancrée sur `first_seen_at` : une session
    d'édition continue ne repousse pas la livraison indéfiniment. Et
    la ligne est retirée à la livraison — c'est ce retrait qui garantit
    l'unicité, pas une relecture d'état.
    """

    __tablename__ = "not_pending"

    receiver_id: Mapped[int] = mapped_column(
        ForeignKey(User.id, ondelete="CASCADE"), nullable=False
    )
    group_key: Mapped[str] = mapped_column(nullable=False)

    message: Mapped[str] = mapped_column(default="")
    url: Mapped[str] = mapped_column(default="")

    # Email facultatif, décrit et non construit : le service de
    # notifications n'a pas à connaître les mailers de chaque module.
    # `mail_template` nomme une classe de `app.services.emails`.
    mail_template: Mapped[str] = mapped_column(default="")
    mail_kwargs: Mapped[dict] = mapped_column(sa.JSON, default=dict)

    first_seen_at: Mapped[arrow.Arrow] = mapped_column(
        ArrowType(timezone=True), default=arrow.utcnow
    )
    last_seen_at: Mapped[arrow.Arrow] = mapped_column(
        ArrowType(timezone=True), default=arrow.utcnow
    )

    receiver: Mapped[User] = relationship(User, foreign_keys=[receiver_id])

    __table_args__ = (
        # Une seule attente par couple : c'est la fusion.
        UniqueConstraint("receiver_id", "group_key", name="uq_not_pending"),
        # Drainage : WHERE first_seen_at <= ? ORDER BY first_seen_at
        Index("ix_not_pending_due", "first_seen_at"),
    )


@service
class PendingNotificationRepository(Repository[PendingNotification]):
    model_type = PendingNotification
