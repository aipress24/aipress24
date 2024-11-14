# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from flask import g, request
from sqlalchemy import select
from werkzeug.exceptions import NotFound, Unauthorized

from app.flask.extensions import db
from app.flask.lib.pages import expose, page
from app.flask.routing import url_for
from app.models.auth import User
from app.services.invoicing import Invoice
from app.services.pdf import to_pdf

from .base import BaseWipPage
from .home import HomePage

__all__ = ["BillingPage"]

COLUMNS_SPECS = {
    "columns": [
        "date",
        {"name": "num_fact", "label": "Num. facture"},
        {"name": "amount", "label": "Montant", "align": "right"},
        {"name": "pdf", "label": "PDF", "width": "1%"},
        {"name": "csv", "label": "CSV", "width": "1%"},
    ],
    "actions": [],
}

# language=jinja2
TEMPLATE = """
{% extends "wip/layout/_base.j2" %}

{% block body_content %}
  {{ make_table(table) }}
{% endblock %}
"""


@page
class BillingPage(BaseWipPage):
    name = "billing"
    label = "Facturation"
    title = "Mon historique de facturation"
    icon = "credit-card"
    template_str = TEMPLATE

    parent = HomePage

    def context(self):
        invoices = self.get_invoices(g.user)
        lines = self.make_lines(invoices)
        table = {
            "specs": COLUMNS_SPECS,
            "lines": lines,
        }
        return {"table": table}

    @expose
    def get_pdf(self):
        invoice = self.get_invoice()
        pdf = to_pdf(invoice)
        filename = f"{invoice.invoice_number}.pdf"
        headers = {
            "content-disposition": f"attachment;filename={filename}",
            "content-type": "text/pdf",
        }
        return pdf, 200, headers

    @expose
    def get_csv(self):
        invoice = self.get_invoice()
        filename = f"{invoice.invoice_number}.csv"
        headers = {
            "content-disposition": f"attachment;filename={filename}",
            "content-type": "text/csv",
        }
        return invoice.to_csv(), 200, headers

    def get_invoice(self) -> Invoice:
        invoice_id = request.args["invoice_id"]
        stmt = select(Invoice).where(Invoice.id == invoice_id)
        invoice = db.session.scalar(stmt)
        if not invoice:
            raise NotFound
        if invoice.owner_id != g.user.id:
            raise Unauthorized
        return invoice

    def get_invoices(self, user: User) -> list[Invoice]:
        stmt = (
            select(Invoice)
            .where(Invoice.owner_id == user.id)
            .order_by(Invoice.invoice_date.desc())
        )
        invoices = db.session.scalars(stmt)
        return list(invoices)

    def make_lines(self, invoices: list[Invoice]) -> list[dict]:
        lines = []
        for invoice in invoices:
            pdf_url = url_for("wip.billing__get_pdf", invoice_id=invoice.id)
            csv_url = url_for("wip.billing__get_csv", invoice_id=invoice.id)
            d = {
                "url": "#",
                "columns": [
                    invoice.invoice_date.strftime("%d/%m/%Y"),
                    invoice.invoice_number,
                    invoice.total / 100,
                    {"type": "download", "value": pdf_url},
                    {"type": "download", "value": csv_url},
                ],
            }
            lines.append(d)
        return lines
