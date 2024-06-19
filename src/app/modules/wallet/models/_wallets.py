# Copyright (c) 2021-2024 - Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

import arrow
import sqlalchemy as sa
from aenum import StrEnum, auto
from sqlalchemy.orm import Mapped, declared_attr, mapped_column, relationship
from sqlalchemy_utils import ArrowType

from app.lib.names import to_snake_case
from app.models.auth import User
from app.models.base import Base
from app.models.mixins import IdMixin
from app.models.orgs import Organisation


class WalletStatus(StrEnum):
    ACTIVE = auto()
    TERMINATED = auto()


class BaseWallet(IdMixin, Base):
    __allow_unmapped__ = True
    __tablename__ = "wal_base_wallet"

    type: Mapped[str] = mapped_column()

    status: Mapped[WalletStatus] = mapped_column(default=WalletStatus.ACTIVE)

    created_at: Mapped[arrow.Arrow] = mapped_column(ArrowType, default=arrow.now)
    terminated_at: Mapped[arrow.Arrow | None] = mapped_column(ArrowType)

    balance: Mapped[int] = mapped_column(default=0)

    @declared_attr
    def __mapper_args__(cls):
        return {
            "polymorphic_identity": to_snake_case(cls.__name__),
            "polymorphic_on": cls.type,
        }

    def terminate(self) -> None:
        self.status = WalletStatus.TERMINATED
        self.terminated_at = arrow.now()

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} {self.id}>"


class IndividualWallet(BaseWallet, Base):
    __tablename__ = "wal_wallet"

    id: Mapped[int] = mapped_column(
        sa.BigInteger, sa.ForeignKey(BaseWallet.id), primary_key=True
    )

    user_id: Mapped[int] = mapped_column(sa.ForeignKey(User.id))
    user: Mapped[User] = relationship(User, back_populates="wallet")

    @property
    def owner_name(self):
        return self.user.name


class CorporateWallet(BaseWallet, Base):
    __tablename__ = "wal_corp_wallet"

    id: Mapped[int] = mapped_column(
        sa.BigInteger, sa.ForeignKey(BaseWallet.id), primary_key=True
    )

    org_id: Mapped[int] = mapped_column(sa.BigInteger, sa.ForeignKey(Organisation.id))
    org: Mapped[Organisation] = relationship(Organisation)

    @property
    def owner_name(self):
        return self.org.name


class EmployeeWallet(BaseWallet, Base):
    __tablename__ = "wal_emp_wallet"

    id: Mapped[int] = mapped_column(
        sa.BigInteger, sa.ForeignKey(BaseWallet.id), primary_key=True
    )

    user_id: Mapped[int] = mapped_column(sa.ForeignKey(User.id))
    user: Mapped[User] = relationship(User)

    org_id: Mapped[int] = mapped_column(sa.BigInteger, sa.ForeignKey(Organisation.id))
    org: Mapped[Organisation] = relationship(Organisation)

    @property
    def owner_name(self) -> str:
        return f"{self.user.name} ({self.org.name})"
