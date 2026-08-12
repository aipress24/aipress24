# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""WORK/Achats — the buyer's article-purchase history.

Per Erick (#0193 – #0196) : every PAID `ArticlePurchase` (consultation,
justificatif, cession, gifted consultation) « converge dans WORK/Achats »
of the member who paid. This is the read-only counterpart of the buy
pop-ups : « show me what I've already spent ».
"""

from __future__ import annotations

from datetime import UTC, datetime
from io import BytesIO
from typing import TYPE_CHECKING

from flask import g, render_template, send_file
from odsgenerator import odsgenerator
from sqlalchemy import or_, select
from sqlalchemy.orm import selectinload
from werkzeug.exceptions import Forbidden

from app.enums import RoleEnum
from app.flask.extensions import db
from app.flask.lib.nav import nav
from app.lib.base62 import base62
from app.modules.wip import blueprint
from app.modules.wire.models import ArticlePurchase, PurchaseStatus
from app.modules.wire.services.purchase_aggregates import (
    get_org_purchase_total,
    get_user_purchase_total,
)

from ._common import get_secondary_menu

if TYPE_CHECKING:
    from app.models.auth import User

_PRODUCT_LABELS: dict[str, str] = {
    "consultation": "Consultation d'article",
    "justificatif": "Justificatif de publication",
    "cession": "Cession de droits",
    "consultation_gift": "Consultation offerte",
}

MONTH_NAMES_FR: dict[int, str] = {
    1: "Janvier",
    2: "Février",
    3: "Mars",
    4: "Avril",
    5: "Mai",
    6: "Juin",
    7: "Juillet",
    8: "Août",
    9: "Septembre",
    10: "Octobre",
    11: "Novembre",
    12: "Décembre",
}


@blueprint.route("/achats")
@nav(icon="shopping-bag", acl=[("Allow", RoleEnum.SELF, "view")])
def achats():
    """Mes achats éditoriaux"""
    user = g.user
    if not user or getattr(user, "is_anonymous", True) or not getattr(user, "id", None):
        return render_template(
            "wip/pages/achats.j2",
            title="Mes achats",
            months=[],
            user_total_eur=0.0,
            org_total_eur=0.0,
            menus={"secondary": get_secondary_menu("achats")},
        )

    user_total_cents = get_user_purchase_total(user.id)
    org_total_cents = get_org_purchase_total(getattr(user, "organisation_id", None))

    months = _list_user_purchases_by_month(user)

    return render_template(
        "wip/pages/achats.j2",
        title="Mes achats",
        months=months,
        user_total_eur=user_total_cents / 100,
        org_total_eur=org_total_cents / 100,
        menus={"secondary": get_secondary_menu("achats")},
    )


@blueprint.route("/achats/export/user/<month>.ods")
def achats_export_user_month(month: str):
    """Export personal purchases for a specific month as an ODS spreadsheet."""
    user = g.user
    if not user or user.is_anonymous:
        raise Forbidden

    ods_bytes = generate_month_achats_ods(user, month, scope="user")
    stream = BytesIO(ods_bytes)
    stream.seek(0)
    filename = f"achats_editoriaux_{month}.ods"
    return send_file(
        stream,
        download_name=filename,
        mimetype="application/vnd.oasis.opendocument.spreadsheet",
        as_attachment=True,
    )


@blueprint.route("/achats/export/org/<month>.ods")
def achats_export_org_month(month: str):
    """Export organisation purchases for a specific month as an ODS spreadsheet."""
    user = g.user
    if not user or user.is_anonymous:
        raise Forbidden

    ods_bytes = generate_month_achats_ods(user, month, scope="org")
    stream = BytesIO(ods_bytes)
    stream.seek(0)
    filename = f"achats_organisation_{month}.ods"
    return send_file(
        stream,
        download_name=filename,
        mimetype="application/vnd.oasis.opendocument.spreadsheet",
        as_attachment=True,
    )


def generate_month_achats_ods(user: User, month_key: str, scope: str = "user") -> bytes:
    """Generate ODS report.

    Args:
        month_key: yyyy-mm.
        scope: "user" (mes achats éditoriaux) or "org" (achats de mon organisation).
    """
    try:
        year_str, month_str = month_key.split("-")
        year, month = int(year_str), int(month_str)
    except (ValueError, AttributeError):
        year, month = 0, 0

    month_label = (
        f"{MONTH_NAMES_FR.get(month, str(month))} {year}" if month else month_key
    )

    months_data = _list_user_purchases_by_month(user)
    target_month = next((m for m in months_data if m["key"] == month_key), None)

    if not target_month:
        user_total = 0.0
        org_total = 0.0
        all_rows = []
    else:
        user_total = target_month["user_total_eur"]
        org_total = target_month["org_total_eur"]
        all_rows = target_month["rows"]

    user_name = (
        f"{getattr(user, 'first_name', '') or ''} {getattr(user, 'last_name', '') or ''}".strip()
        or getattr(user, "email", "")
    )
    org = getattr(user, "organisation", None)
    bw_name = (
        getattr(org, "bw_name", "")
        or getattr(org, "name", "")
        or getattr(user, "organisation_name", "")
    )

    if scope == "org":
        title_header = "AiPRESS24 - Achats de mon Business Wall"
        bw_str = bw_name or "Non renseigné"
        entity_line = {"row": [{"value": f"Business Wall : {bw_str}", "style": "bold"}]}
        total_value = float(f"{org_total:.2f}")
        total_value_string = f"{total_value:.2f} € HT"
        total_header_label = (
            f"Cumul des achats du Business Wall ({bw_str}) : {total_value_string}"
        )
        rows = [r for r in all_rows if r.get("is_paid")]
        sheet_name = f"Achats Org {month_key}"
    else:
        title_header = "AiPRESS24 - Mes Achats Éditoriaux"
        entity_line = {
            "row": [{"value": f"Utilisateur : {user_name}", "style": "bold"}]
        }
        total_value = float(f"{user_total:.2f}")
        total_value_string = f"{total_value:.2f} € HT"
        total_header_label = f"Cumul des achats éditoriaux : {total_value_string}"
        rows = [r for r in all_rows if r.get("is_my_purchase") and r.get("is_paid")]
        sheet_name = f"Mes Achats {month_key}"

    export_now_str = datetime.now(UTC).strftime("%d/%m/%Y %H:%M")

    sheet_table: list[dict] = [
        {"row": [{"value": title_header, "style": "bold"}]},
        entity_line,
        {"row": [{"value": f"Période : {month_label}", "style": "bold"}]},
        {"row": [{"value": f"Export à la date du : {export_now_str}"}]},
        {"row": []},
        {"row": [{"value": total_header_label}]},
        {"row": []},
        {
            "row": [
                {"value": "Date", "style": "bold_left_bg_gray_grid_06pt"},
                {"value": "Type d'achat", "style": "bold_left_bg_gray_grid_06pt"},
                {"value": "Titre de l'article", "style": "bold_left_bg_gray_grid_06pt"},
                {"value": "Acheteur", "style": "bold_left_bg_gray_grid_06pt"},
                {"value": "Montant (HT €)", "style": "bold_left_bg_gray_grid_06pt"},
                {"value": "Statut", "style": "bold_left_bg_gray_grid_06pt"},
            ],
        },
    ]

    for row in rows:
        dt_str = row["date"].strftime("%d/%m/%Y") if row.get("date") else ""
        buyer = row["buyer_name"]
        status_str = "Remboursé" if row.get("is_refunded") else "Payé"
        sheet_table.append(
            {
                "row": [
                    {"value": dt_str},
                    {"value": row["type_label"]},
                    {"value": row["post_title"]},
                    {"value": buyer},
                    {
                        "value": float(f"{row['amount_eur']:.2f}"),
                        "style": "cell_decimal2",
                    },
                    {"value": status_str},
                ]
            }
        )
    sheet_table.append(
        {
            "row": [
                {"colspanned": 4, "value": "Total :", "style": "right_grid_06pt"},
                None,
                None,
                None,
                {"value": total_value, "style": "decimal2_grid_06pt"},
                {"value": "", "style": "right_grid_06pt"},
            ],
        }
    )

    content = {
        "body": [
            {
                "name": sheet_name,
                "width": [
                    "2.5cm",  # Date
                    "4.5cm",  # Type d'achat
                    "12cm",  # Titre de l'article
                    "6cm",  # Acheteur
                    "3cm",  # Montant (HT €)
                    "2cm",  # Statut
                ],
                "table": sheet_table,
            }
        ]
    }
    return odsgenerator.ods_bytes(content)


def _list_user_purchases_by_month(user: User) -> list[dict]:
    """Build monthly purchase groups for /wip/achats.

    Group purchases by month, calculating
        - "Cumul de mes achats éditoriaux"
        - "Cumul des achats de mon organisation"
    """
    if not user or getattr(user, "is_anonymous", True) or not getattr(user, "id", None):
        return []

    purchases = _fetch_purchases_for_user_and_org(user)
    grouped = _group_purchases_by_month(purchases)

    return [
        _build_month_summary(year, month, items, user)
        for (year, month), items in sorted(grouped.items(), reverse=True)
    ]


def _fetch_purchases_for_user_and_org(user: User) -> list[ArticlePurchase]:
    """Query PAID and REFUNDED purchases for user and their organisation."""
    from app.models.auth import User as UserModel

    conditions = [ArticlePurchase.owner_id == user.id]
    if getattr(user, "organisation_id", None):
        conditions.append(UserModel.organisation_id == user.organisation_id)

    stmt = (
        select(ArticlePurchase)
        .options(
            selectinload(ArticlePurchase.post), selectinload(ArticlePurchase.owner)
        )
        .join(UserModel, ArticlePurchase.owner_id == UserModel.id)
        .where(or_(*conditions))
        .where(
            ArticlePurchase.status.in_([PurchaseStatus.PAID, PurchaseStatus.REFUNDED])
        )
        .order_by(
            ArticlePurchase.paid_at.desc().nullslast(),
            ArticlePurchase.timestamp.desc(),
        )
    )
    return list(db.session.scalars(stmt).unique())


def _group_purchases_by_month(
    purchases: list[ArticlePurchase],
) -> dict[tuple[int, int], list[ArticlePurchase]]:
    """Group purchases by (year, month)"""
    grouped: dict[tuple[int, int], list[ArticlePurchase]] = {}
    for p in purchases:
        dt = p.paid_at or p.timestamp
        if dt is None:
            continue
        key = (dt.year, dt.month)
        grouped.setdefault(key, []).append(p)
    return grouped


def _build_month_summary(
    year: int, month: int, items: list[ArticlePurchase], user: User
) -> dict:
    """Build summary dictionary for a specific month."""
    month_label = f"{MONTH_NAMES_FR.get(month, str(month))} {year}"

    user_cents = sum(
        p.amount_cents or 0
        for p in items
        if p.owner_id == user.id and p.status == PurchaseStatus.PAID
    )

    org_cents = sum(
        p.amount_cents or 0
        for p in items
        if p.status == PurchaseStatus.PAID
        and (
            (
                user.organisation_id
                and getattr(p.owner, "organisation_id", None) == user.organisation_id
            )
            or p.owner_id == user.id
        )
    )

    rows = [_format_purchase_row(p, user) for p in items]

    return {
        "key": f"{year}-{month:02d}",
        "label": month_label,
        "user_total_eur": user_cents / 100,
        "org_total_eur": org_cents / 100,
        "rows": rows,
    }


def _format_purchase_row(p: ArticlePurchase, user: User) -> dict:
    """Format a single ArticlePurchase into a display dictionary."""
    post = p.post
    dt = p.paid_at or p.timestamp
    buyer_name = f"{p.owner.first_name} {p.owner.last_name}".strip() or p.owner.email

    return {
        "id": p.id,
        "date": dt,
        "type_label": _PRODUCT_LABELS.get(str(p.product_type), str(p.product_type)),
        "post_title": getattr(post, "title", "")
        or getattr(post, "titre", "")
        or "(article)",
        "post_url": f"/wire/item/{base62.encode(post.id)}" if post else "#",
        "amount_eur": (p.amount_cents or 0) / 100,
        "status": str(p.status),
        "is_paid": p.status == PurchaseStatus.PAID,
        "is_refunded": p.status == PurchaseStatus.REFUNDED,
        "is_my_purchase": p.owner_id == user.id,
        "buyer_name": buyer_name,
    }
