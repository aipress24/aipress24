# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

# TODO
from __future__ import annotations

from sqlalchemy import BigInteger, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.models.mixins import IdMixin, Owned, Timestamped

from . import EditorialProduct

__all__ = ["Purchase"]


class Purchase(IdMixin, Owned, Timestamped, Base):
    __tablename__ = "mkp_purchase"

    product_id: Mapped[int] = mapped_column(BigInteger, ForeignKey(EditorialProduct.id))
    product = relationship(EditorialProduct, foreign_keys=[product_id])
