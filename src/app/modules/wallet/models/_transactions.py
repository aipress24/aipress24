# Copyright (c) 2021-2024 - Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.models.mixins import IdMixin, Owned, Timestamped

from ._wallets import BaseWallet


class BaseTransaction(IdMixin, Owned, Timestamped):
    amount: Mapped[int]
    currency: Mapped[str] = mapped_column(default="EUR")
    label: Mapped[str] = mapped_column(default="")


class WalletTransaction(BaseTransaction, Base):
    __tablename__ = "wal_transaction"

    from_wallet_id: Mapped[int] = mapped_column(sa.ForeignKey(BaseWallet.id))
    to_wallet_id: Mapped[int] = mapped_column(sa.ForeignKey(BaseWallet.id))

    from_wallet: Mapped[BaseWallet] = relationship(
        BaseWallet,
        # back_populates="transactions_from",
        foreign_keys=[from_wallet_id],
    )
    to_wallet: Mapped[BaseWallet] = relationship(
        BaseWallet,
        # back_populates="transactions",
        foreign_keys=[to_wallet_id],
    )

    label: Mapped[str] = mapped_column(default="")
    description: Mapped[str] = mapped_column(default="")

    # TODO
    status = "pending"


class WalletPayment(BaseTransaction, Base):
    __tablename__ = "wal_payment"

    wallet_id: Mapped[int] = mapped_column(sa.ForeignKey(BaseWallet.id))
    account_iban: Mapped[str]
