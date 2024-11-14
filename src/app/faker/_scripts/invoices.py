# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from flask_super.registry import register

from app.flask.extensions import db
from app.models.auth import User
from app.services.invoicing import Invoice, InvoiceLine

from .base import FakerScript


@register
class InvoiceFakerScript(FakerScript):
    name = "invoices"
    model_class = Invoice

    def generate(self) -> None:
        users = db.session.query(User).all()
        for user in users:
            self.gen_fake_invoices(user)

        db.session.flush()

    def gen_fake_invoices(self, user: User) -> None:
        for i in range(1, 12):
            month = f"{i:02d}"
            invoice_date = f"2022-{month}-01"
            self.counter = (self.counter + 1) % 10000
            invoice_number = f"FAC-2022-{month}-{self.counter:04d}"

            invoice = Invoice(
                owner_id=user.id,
                invoice_number=invoice_number,
                invoice_date=invoice_date,
            )

            unit_price = 5000
            quantity = 1
            total = unit_price * quantity
            line = InvoiceLine(
                invoice=invoice,
                description="Abonnement GOLD",
                quantity=quantity,
                unit_price=unit_price,
                total=total,
            )
            assert line in invoice.lines

            invoice.total = sum(line.total for line in invoice.lines)

            db.session.add(invoice)

        db.session.flush()
