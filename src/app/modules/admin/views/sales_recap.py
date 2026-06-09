# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Admin sales / purchases recap (tickets #0193–#0196).

Two read-only dashboards used by the AiPRESS24 admin :

- `/admin/sales-per-media` — total PAID sales per media organisation
  (= the post publisher). Used to drive the manual virements aux
  médias at month-end.
- `/admin/purchases-per-org` — total PAID purchases per buyer
  organisation. Used to drive per-org invoicing reconciliation.

Both tables are sorted by amount desc so the largest-impact rows are
at the top. The admin blueprint enforces ADMIN role in `before_request`.
"""

from __future__ import annotations

from flask import render_template

from app.flask.lib.nav import nav
from app.modules.admin import blueprint
from app.modules.wire.services.purchase_aggregates import (
    list_purchases_per_org,
    list_sales_per_media,
)


@blueprint.route("/sales-per-media")
@nav(parent="index", icon="banknotes", label="Ventes par média")
def sales_per_media():
    """Recap des ventes éditoriales par média."""
    rows = [
        {"org_id": org_id, "org_name": name, "total_eur": cents / 100}
        for org_id, name, cents in list_sales_per_media()
    ]
    total_eur = sum(r["total_eur"] for r in rows)
    return render_template(
        "admin/pages/sales_recap.j2",
        title="Ventes par média",
        rows=rows,
        total_eur=total_eur,
        header="Ventes par média",
        column_label="Média",
        empty_message="Aucune vente éditoriale enregistrée à ce jour.",
    )


@blueprint.route("/purchases-per-org")
@nav(parent="index", icon="shopping-bag", label="Achats par organisation")
def purchases_per_org():
    """Recap des achats éditoriaux par organisation acheteuse."""
    rows = [
        {"org_id": org_id, "org_name": name, "total_eur": cents / 100}
        for org_id, name, cents in list_purchases_per_org()
    ]
    total_eur = sum(r["total_eur"] for r in rows)
    return render_template(
        "admin/pages/sales_recap.j2",
        title="Achats par organisation",
        rows=rows,
        total_eur=total_eur,
        header="Achats par organisation",
        column_label="Organisation",
        empty_message="Aucun achat éditorial enregistré à ce jour.",
    )
