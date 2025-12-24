# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""WIP billing page."""

from __future__ import annotations

from flask import g, render_template, request
from sqlalchemy import select
from werkzeug.exceptions import NotFound, Unauthorized

from app.enums import RoleEnum
from app.flask.extensions import db
from app.flask.lib.nav import nav
from app.flask.routing import url_for
from app.models.auth import User
from app.modules.wip import blueprint
from app.services.invoicing import Invoice
from app.services.pdf import to_pdf

from ._common import get_secondary_menu

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

TEMPLATE = """
{% extends "wip/layout/_base.j2" %}

{% block body_content %}
  {{ make_table(table) }}
{% endblock %}
"""


@blueprint.route("/billing")
@nav(icon="credit-card", acl=[("Allow", RoleEnum.SELF, "view")])
def billing():
    """Facturation"""
    invoices = _get_invoices(g.user)
    lines = _make_lines(invoices)
    table = {
        "specs": COLUMNS_SPECS,
        "lines": lines,
    }
    return render_template(
        "wip/pages/billing.j2",
        title="Mon historique de facturation",
        table=table,
        menus={"secondary": get_secondary_menu("billing")},
    )


@blueprint.route("/billing/get_pdf")
@nav(hidden=True)
def billing_get_pdf():
    """Download invoice as PDF."""
    invoice = _get_invoice()
    pdf = to_pdf(invoice)
    filename = f"{invoice.invoice_number}.pdf"
    headers = {
        "content-disposition": f"attachment;filename={filename}",
        "content-type": "text/pdf",
    }
    return pdf, 200, headers


@blueprint.route("/billing/get_csv")
@nav(hidden=True)
def billing_get_csv():
    """Download invoice as CSV."""
    invoice = _get_invoice()
    filename = f"{invoice.invoice_number}.csv"
    headers = {
        "content-disposition": f"attachment;filename={filename}",
        "content-type": "text/csv",
    }
    return invoice.to_csv(), 200, headers


def _get_invoice() -> Invoice:
    """Get invoice by ID from request args."""
    invoice_id = request.args["invoice_id"]
    stmt = select(Invoice).where(Invoice.id == invoice_id)
    invoice = db.session.scalar(stmt)
    if not invoice:
        raise NotFound
    if invoice.owner_id != g.user.id:
        raise Unauthorized
    return invoice


def _get_invoices(user: User) -> list[Invoice]:
    """Get all invoices for user."""
    stmt = (
        select(Invoice)
        .where(Invoice.owner_id == user.id)
        .order_by(Invoice.invoice_date.desc())
    )
    invoices = db.session.scalars(stmt)
    return list(invoices)


def _make_lines(invoices: list[Invoice]) -> list[dict]:
    """Build table lines from invoices."""
    lines = []
    for invoice in invoices:
        pdf_url = url_for("wip.billing_get_pdf", invoice_id=invoice.id)
        csv_url = url_for("wip.billing_get_csv", invoice_id=invoice.id)
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
