# Copyright (c) 2021-2024 - Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta
from io import BytesIO
from typing import Any
from zoneinfo import ZoneInfo

from flask import send_file
from odsgenerator import odsgenerator
from sqlalchemy import desc, false, nulls_last, select, true

from app.constants import BW_TRIGGER_LABEL, LABEL_INSCRIPTION_VALIDEE
from app.flask.extensions import db
from app.flask.lib.pages import Page, page
from app.models.auth import User

from .. import blueprint
from .home import AdminHomePage

ODS_INSCRIPTIONS_BASE = {
    "body": [
        {
            "name": "inscriptions",
            "table": [
                {"row": ["AIPress24"], "style": "bold"},
                {
                    "row": ["Statistiques d’inscriptions depuis le "],
                    "style": "default_table_row",
                },
                {"row": [], "style": "default_table_row"},
                {"row": [], "style": "default_table_row"},
                {
                    "row": [
                        {"style": "ce1", "value": "Inscription"},
                        {"style": "ce1", "value": "Validation"},
                        {"style": "ce1", "value": "Commentaire"},
                        {"style": "ce1", "value": "BW validé"},
                        {"style": "ce1", "value": "Profil"},
                        {"style": "ce1", "value": "Nom"},
                        {"style": "ce1", "value": "Prénom"},
                        {"style": "ce1", "value": "Civilité"},
                        {"style": "ce1", "value": "Pseudo"},
                        {"style": "ce1", "value": "Carte Presse"},
                        {"style": "ce1", "value": "Email"},
                        {"style": "ce1", "value": "Mobile"},
                        {"style": "ce1", "value": "Ok repas"},
                        {"style": "ce1", "value": "Ok verre"},
                        {"style": "ce1", "value": "Présentation"},
                        {"style": "ce1", "value": "Organisation"},
                        {"style": "ce1", "value": "Compétences"},
                        {"style": "ce1", "value": "Compétences journalisme"},
                        {"style": "ce1", "value": "Expériences"},
                        {"style": "ce1", "value": "Formations"},
                        {"style": "ce1", "value": "Langues"},
                        {"style": "ce1", "value": "Métier"},
                        {"style": "ce1", "value": "Métier détail"},
                    ],
                    "style": "default_table_row",
                },
            ],
            "width": [
                "2.9cm",
                "2.9cm",
                "5cm",
                "4cm",
                "12cm",
                "4cm",
                "4cm",
                "1.4cm",
                "4cm",
                "4cm",
                "6cm",
                "3cm",
                "1.4cm",
                "1.4cm",
                "12cm",
                "4cm",
                "8cm",
                "8cm",
                "8cm",
                "8cm",
                "6cm",
                "8cm",
                "8cm",
            ],
        },
    ],
    "styles": [
        {
            "definition": '<style:style style:family="table-cell" style:parent-style-name="Default">\n  <style:table-cell-properties fo:background-color="#eeeeee"/>\n  <style:text-properties fo:font-weight="bold" style:font-weight-asian="bold" style:font-weight-complex="bold"/>\n</style:style>\n',
            "name": "ce1",
        },
        {
            "definition": '<style:style style:family="table-cell" style:parent-style-name="Default">\n  <style:table-cell-properties style:text-align-source="fix" style:repeat-content="false"/>\n  <style:paragraph-properties fo:text-align="start" fo:margin-left="0.101cm"/>\n  <style:text-properties fo:font-size="8pt" style:font-size-asian="8pt" style:font-size-complex="8pt"/>\n</style:style>\n',
            "name": "ce3",
        },
        {
            "definition": '<style:style style:family="table-row">\n  <style:table-row-properties style:row-height="0.452cm" fo:break-before="auto" style:use-optimal-row-height="true"/>\n</style:style>\n',
            "name": "default_table_row",
        },
    ],
}

ODS_MODIFICATIONS_BASE = {
    "body": [
        {
            "name": "inscriptions",
            "table": [
                {"row": ["AIPress24"], "style": "bold"},
                {
                    "row": ["Statistiques d’inscriptions depuis le "],
                    "style": "default_table_row",
                },
                {"row": [], "style": "default_table_row"},
                {"row": [], "style": "default_table_row"},
                {
                    "row": [
                        {"style": "ce1", "value": "Inscription"},
                        {"style": "ce1", "value": "Validation"},
                        {"style": "ce1", "value": "Commentaire"},
                        {"style": "ce1", "value": "BW validé"},
                        {"style": "ce1", "value": "Profil"},
                        {"style": "ce1", "value": "Nom"},
                        {"style": "ce1", "value": "Prénom"},
                        {"style": "ce1", "value": "Civilité"},
                        {"style": "ce1", "value": "Pseudo"},
                        {"style": "ce1", "value": "Carte Presse"},
                        {"style": "ce1", "value": "Email"},
                        {"style": "ce1", "value": "Mobile"},
                        {"style": "ce1", "value": "Ok repas"},
                        {"style": "ce1", "value": "Ok verre"},
                        {"style": "ce1", "value": "Présentation"},
                        {"style": "ce1", "value": "Organisation"},
                        {"style": "ce1", "value": "Compétences"},
                        {"style": "ce1", "value": "Compétences journalisme"},
                        {"style": "ce1", "value": "Expériences"},
                        {"style": "ce1", "value": "Formations"},
                        {"style": "ce1", "value": "Langues"},
                        {"style": "ce1", "value": "Métier"},
                        {"style": "ce1", "value": "Métier détail"},
                    ],
                    "style": "default_table_row",
                },
            ],
            "width": [
                "2.9cm",
                "2.9cm",
                "5cm",
                "4cm",
                "12cm",
                "4cm",
                "4cm",
                "1.4cm",
                "4cm",
                "4cm",
                "6cm",
                "3cm",
                "1.4cm",
                "1.4cm",
                "12cm",
                "4cm",
                "8cm",
                "8cm",
                "8cm",
                "8cm",
                "6cm",
                "8cm",
                "8cm",
            ],
        },
    ],
    "styles": [
        {
            "definition": '<style:style style:family="table-cell" style:parent-style-name="Default">\n  <style:table-cell-properties fo:background-color="#eeeeee"/>\n  <style:text-properties fo:font-weight="bold" style:font-weight-asian="bold" style:font-weight-complex="bold"/>\n</style:style>\n',
            "name": "ce1",
        },
        {
            "definition": '<style:style style:family="table-cell" style:parent-style-name="Default">\n  <style:table-cell-properties style:text-align-source="fix" style:repeat-content="false"/>\n  <style:paragraph-properties fo:text-align="start" fo:margin-left="0.101cm"/>\n  <style:text-properties fo:font-size="8pt" style:font-size-asian="8pt" style:font-size-complex="8pt"/>\n</style:style>\n',
            "name": "ce3",
        },
        {
            "definition": '<style:style style:family="table-row">\n  <style:table-row-properties style:row-height="0.452cm" fo:break-before="auto" style:use-optimal-row-height="true"/>\n</style:style>\n',
            "name": "default_table_row",
        },
    ],
}


@page
class AdminExportPage(Page):
    name = "exports"
    label = "Exports"
    title = "Exports"
    icon = "user-group"

    template = "admin/pages/exports.j2"
    parent = AdminHomePage

    ds_class = None
    table_class = None

    def menus(self):
        # Lazy import to prevent circular import
        from .menu import make_menu

        name = self.name
        return {
            "secondary": make_menu(name),
        }


def new_inscriptions_users(start_date: datetime) -> list[User]:
    stmt = (
        select(User)
        .where(
            # all users, wether inscription validated or not :
            # User.active == false(),
            User.is_clone == false(),
            User.deleted == false(),
            User.date_submit >= start_date,
        )
        .order_by(nulls_last(desc(User.date_submit)))
    )
    return list(db.session.scalars(stmt))


def new_modifications_users(start_date: datetime) -> list[User]:
    stmt = (
        select(User)
        .where(
            User.active == true(),
            User.is_clone == false(),
            User.deleted == false(),
            User.user_date_update >= start_date,
            User.user_valid_comment != LABEL_INSCRIPTION_VALIDEE,
        )
        .order_by(nulls_last(desc(User.user_date_update)))
    )
    return list(db.session.scalars(stmt))


def list_to_str(list_or_str: list | str | Any) -> str:
    if isinstance(list_or_str, list):
        return ", ".join(str(x) for x in list_or_str)
    return str(list_or_str)


def user_row_data(user: User) -> list[Any]:
    profile = user.profile
    return [
        user.date_submit,
        user.user_date_valid,
        user.user_valid_comment,
        BW_TRIGGER_LABEL.get(profile.get_first_bw_trigger(), ""),
        # profile.get_first_bw_trigger().replace("trigger_", "").replace("_", " "),
        profile.profile_label,
        user.last_name,
        user.first_name,
        user.gender,
        profile.info_personnelle["pseudo"],
        profile.info_personnelle["no_carte_presse"],
        user.email,
        user.tel_mobile,
        profile.info_personnelle["macaron_repas"],
        profile.info_personnelle["macaron_verre"],
        profile.presentation,
        profile.organisation_name,
        list_to_str(profile.match_making["competences"]),
        list_to_str(profile.match_making["competences_journalisme"]),
        list_to_str(profile.match_making["experiences"]),
        list_to_str(profile.match_making["formations"]),
        list_to_str(profile.match_making["langues"]),
        list_to_str(profile.match_making["metier"]),
        list_to_str(profile.match_making["metier_detail"]),
    ]


def make_row(user: User) -> dict[str, Any]:
    row = user_row_data(user)
    return {"row": row, "style": "default_table_row"}


def fill_content_inscriptions(
    base: dict[str, Any], start_date: datetime, date_now: datetime
) -> None:
    table = base["body"][0]["table"]  # list of row
    date_string = start_date.strftime("%d/%m/%Y")
    table[1]["row"] = [
        {"value": f"Demandes d'inscriptions depuis le {date_string}", "style": "bold"}
    ]
    table[2]["row"] = [
        {
            "value": date_now.isoformat(" ", "minutes"),
            "style": "ce3",
        }
    ]
    for user in new_inscriptions_users(start_date):
        table.append(make_row(user))


def fill_content_modifications(
    base: dict[str, Any], start_date: datetime, date_now: datetime
) -> None:
    table = base["body"][0]["table"]  # list of row
    date_string = start_date.strftime("%d/%m/%Y")
    table[1]["row"] = [
        {"value": f"Modification importantes depuis le {date_string}", "style": "bold"}
    ]
    table[2]["row"] = [
        {
            "value": date_now.isoformat(" ", "minutes"),
            "style": "ce3",
        }
    ]
    for user in new_modifications_users(start_date):
        table.append(make_row(user))


def export_inscription_since(start_date: datetime, date_now: datetime) -> bytes:
    base = deepcopy(ODS_INSCRIPTIONS_BASE)
    fill_content_inscriptions(base, start_date, date_now)
    return odsgenerator.ods_bytes(base)


def export_modification_since(start_date: datetime, date_now: datetime) -> bytes:
    base = deepcopy(ODS_MODIFICATIONS_BASE)
    fill_content_modifications(base, start_date, date_now)
    return odsgenerator.ods_bytes(base)


def export_inscription() -> tuple[bytes, str]:
    date_now = datetime.today().astimezone(ZoneInfo("Europe/Paris"))
    start_date = date_now - timedelta(days=31)
    start_date.replace(hour=0, minute=0, second=0, microsecond=0)
    filename = f"inscriptions_depuis_{start_date.strftime('%Y-%m-%d')}.ods"
    document = export_inscription_since(start_date, date_now)
    return document, filename


def export_modification() -> tuple[bytes, str]:
    date_now = datetime.today().astimezone(ZoneInfo("Europe/Paris"))
    start_date = date_now - timedelta(days=31)
    start_date.replace(hour=0, minute=0, second=0, microsecond=0)
    filename = f"modifications_depuis_{start_date.strftime('%Y-%m-%d')}.ods"
    document = export_modification_since(start_date, date_now)
    return document, filename


@blueprint.route("/export_inscription")
def export_inscription_route():
    document, filename = export_inscription()
    stream = BytesIO(document)
    stream.seek(0)
    return send_file(
        stream,
        mimetype="application/vnd.oasis.opendocument.spreadsheet",
        download_name=filename,
        as_attachment=True,
    )


@blueprint.route("/export_modification")
def export_modification_route():
    document, filename = export_modification()
    stream = BytesIO(document)
    stream.seek(0)
    return send_file(
        stream,
        mimetype="application/vnd.oasis.opendocument.spreadsheet",
        download_name=filename,
        as_attachment=True,
    )
