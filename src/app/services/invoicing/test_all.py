# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

import arrow
from flask_sqlalchemy import SQLAlchemy

from app.models.auth import User
from app.services.invoicing._models import Invoice, InvoiceLine

INVOICE_LINES = [
    {
        "description": "Abonnement GOLD - du 01/01/2023 au 31/12/2023",
        "quantity": 1,
        "unit_price": 5000,
        "total": 5000,
    },
]


def test_create_invoice(db: SQLAlchemy) -> None:
    user = User(email="toto@toto.com")
    invoice = Invoice()
    for d in INVOICE_LINES:
        invoice_line = InvoiceLine(**d)
        invoice.lines.append(invoice_line)

    invoice.owner = user
    invoice.invoice_number = "INV-2021-0001"
    invoice.invoice_date = arrow.get("2021-01-01")
    invoice.total = 5000

    db.session.add(invoice)
    db.session.flush()
