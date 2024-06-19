# Copyright (c) 2021-2024 - Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from app.services.invoicing import Invoice

from .base import generate_pdf, to_pdf


@to_pdf.register
def _to_pdf(invoice: Invoice, template=None) -> bytes:
    lines = []
    for line in invoice.lines:
        lines.append(
            {
                "description": line.description,
                "quantity": line.quantity,
                "unit_price": line.unit_price / 100,
                "total": line.total / 100,
            }
        )
    data = {
        "invoice_date": invoice.invoice_date,
        "invoice_number": invoice.invoice_number,
        "invoice_total": invoice.total / 100,
        "invoice_lines": lines,
    }
    return generate_pdf(data, template or "invoice-pdf.j2")
