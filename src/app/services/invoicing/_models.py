# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

import csv
from io import StringIO

from arrow import arrow
from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy_utils import ArrowType

from app.models.auth import User
from app.models.base import Base
from app.models.mixins import IdMixin, Timestamped


class InvoiceLine(IdMixin, Base):
    __tablename__ = "inv_line"

    invoice_id: Mapped[int] = mapped_column(ForeignKey("inv_invoice.id"))
    invoice: Mapped[Invoice] = relationship("Invoice", back_populates="lines")

    description: Mapped[str]
    quantity: Mapped[int]
    unit_price: Mapped[int]
    total: Mapped[int]


class Invoice(IdMixin, Timestamped, Base):
    __tablename__ = "inv_invoice"

    invoice_number: Mapped[str]
    invoice_date: Mapped[arrow.Arrow] = mapped_column(ArrowType(timezone=True))

    owner_id: Mapped[int] = mapped_column(ForeignKey(User.id), nullable=False)
    owner: Mapped[User] = relationship(User, foreign_keys=[owner_id])

    lines: Mapped[list[InvoiceLine]] = relationship(
        InvoiceLine, back_populates="invoice"
    )

    total: Mapped[int]

    def to_csv(self):
        with StringIO() as csvfile:
            write = csv.writer(csvfile)
            write.writerow(
                [
                    "description",
                    "quantity",
                    "unit_price (EUR)",
                    "total (EUR)",
                ]
            )
            for line in self.lines:
                write.writerow(
                    [
                        line.description,
                        line.quantity,
                        line.unit_price / 100,
                        line.total / 100,
                    ]
                )
            return csvfile.getvalue()
