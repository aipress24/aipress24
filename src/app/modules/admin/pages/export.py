# Copyright (c) 2021-2024 - Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from collections import namedtuple
from datetime import datetime, timedelta
from io import BytesIO
from typing import Any
from zoneinfo import ZoneInfo

from arrow import Arrow
from flask import send_file
from odsgenerator import odsgenerator
from sqlalchemy import desc, false, nulls_last, select, true

from app.constants import BW_TRIGGER_LABEL, LABEL_INSCRIPTION_VALIDEE
from app.flask.extensions import db
from app.flask.lib.pages import Page, page
from app.models.auth import KYCProfile, User

from .. import blueprint
from .home import AdminHomePage

FieldColumn = namedtuple("FieldColumn", "name header width")  # noqa: PYI024


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


class ExporterInscriptions:
    sheet_name = "Inscriptions"
    columns = [
        # "submited_at",
        # "validated_at",
        "validation_status",
        "bw_trigger",
        "profile_label",
        "last_name",
        "first_name",
        "gender",
        "pseudo",
        "no_carte_presse",
        "email",
        "tel_mobile",
        "macaron_repas",
        "macaron_verre",
        "presentation",
        "organisation_name",
        "competences",
        "competences_journalisme",
        "experiences",
        "formations",
        "langues",
        "metier",
        "metier_detail",
    ]

    def __init__(self) -> None:
        self.date_now: datetime = None  # type: ignore
        self.start_date: datetime = None  # type: ignore
        self.document: bytes = b""
        self.columns_definition: dict[str, FieldColumn] = {}
        self.sheet = {"name": self.sheet_name, "table": []}

    @property
    def title(self) -> str:
        dt = self.start_date.strftime("%d/%m/%Y")
        return f"Demandes d'inscriptions depuis le {dt}"

    @property
    def filename(self) -> str:
        return f"inscriptions_depuis_{self.start_date.strftime('%Y-%m-%d')}.ods"

    def run(self) -> None:
        self.make_sheet()
        content = {"body": [self.sheet]}
        self.document = odsgenerator.ods_bytes(content)

    def do_start_date(self) -> None:
        self.date_now = datetime.today().astimezone(ZoneInfo("Europe/Paris"))
        start = self.date_now - timedelta(days=31)
        self.start_date = start.replace(hour=0, minute=0, second=0, microsecond=0)

    def init_columns_definition(self) -> None:
        text3 = "3cm"
        text4 = "4cm"
        text5 = "5cm"
        text6 = "6cm"
        text8 = "8cm"
        text12 = "12cm"
        short = "1.4cm"
        small = "2cm"
        fields = [
            FieldColumn("bw_trigger", "BW validé", text5),
            FieldColumn("competences", "Compétences", text8),
            FieldColumn("competences_journalisme", "Compétences journalisme", text8),
            FieldColumn("submited_at", "Inscription", text3),
            FieldColumn("email", "Email", text6),
            FieldColumn("experiences", "Expériences", text12),
            FieldColumn("first_name", "Prénom", text4),
            FieldColumn("formations", "Formations", text12),
            FieldColumn("gender", "Civilité", short),
            FieldColumn("id", "ID", short),
            FieldColumn("langues", "Langues", text8),
            FieldColumn("last_login_at", "Last login", text3),
            FieldColumn("last_name", "Nom", text4),
            FieldColumn("macaron_hebergement", "Hébergement", small),
            FieldColumn("macaron_repas", "Repas", small),
            FieldColumn("macaron_verre", "Verre", small),
            FieldColumn("metier", "Métier", text8),
            FieldColumn("metier_detail", "Métier détail", text8),
            FieldColumn("no_carte_presse", "Carte Presse", text4),
            FieldColumn("organisation_name", "Organisation", text5),
            FieldColumn("presentation", "Présentation", text12),
            FieldColumn("profile_label", "Profil", text12),
            FieldColumn("pseudo", "Pseudo", text4),
            FieldColumn("roles", "Rôles", text3),
            FieldColumn("tel_mobile", "Mobile", text3),
            FieldColumn("validated_at", "Validation", text3),
            FieldColumn("validation_status", "Commentaire", text5),
        ]
        self.columns_definition = {f.name: f for f in fields}

    @staticmethod
    def list_to_str(list_or_str: list | str | Any) -> str:
        if isinstance(list_or_str, list):
            return ", ".join(str(x) for x in list_or_str)
        return str(list_or_str)

    def cell_value(
        self,
        user: User,
        profile: KYCProfile,
        name: str,
    ) -> str | datetime | int | bool:
        match name:
            case (
                "id"
                | "validation_status"
                | "last_login_at"
                | "login_count"
                | "gcu_acceptation"
                | "gcu_acceptation_date"
                | "last_name"
                | "first_name"
                | "gender"
                | "email"
                | "email_secours"
                | "tel_mobile"
                | "status"
                | "karma"
                | "organisation_name"
            ):
                value = getattr(user, name)
            case "submited_at":
                value = user.submited_at
                if isinstance(value, Arrow):
                    value = value.datetime
            case "validated_at":
                value = user.validated_at
                if isinstance(value, Arrow):
                    value = value.datetime
            case "modified_at":
                value = user.modified_at
                if isinstance(value, Arrow):
                    value = value.datetime
            case "roles":
                value = [x.name for x in getattr(user, name)]
            case "profile_label" | "presentation":
                value = getattr(profile, name)
            case (
                "pseudo"
                | "no_carte_presse"
                | "macaron_hebergement"
                | "macaron_repas"
                | "macaron_verre"
            ):
                value = profile.info_personnelle.get(name)
            case (
                "adresse_pro"
                | "compl_adresse_pro"
                | "fonctions_ass_syn"
                | "fonctions_ass_syn_detail"
                | "fonctions_journalisme"
                | "fonctions_org_priv"
                | "fonctions_org_priv_detail"
                | "fonctions_pol_adm"
                | "fonctions_pol_adm_detail"
                | "ligne_directe"
                | "nom_adm"
                | "nom_agence_rp"
                | "nom_group_com"
                | "nom_groupe_presse"
                | "nom_media"
                | "nom_media_instit"
                | "nom_orga"
                | "pays_zip_ville"
                | "pays_zip_ville_detail"
                | "taille_orga"
                | "tel_standard"
                | "type_agence_rp"
                | "type_entreprise_media"
                | "type_orga"
                | "type_orga_detail"
                | "type_presse_et_media"
                | "url_site_web"
            ):
                value = profile.info_professionnelle.get(name)
            case (
                "competences"
                | "competences_journalisme"
                | "experiences"
                | "formations"
                | "hobbies"
                | "interet_ass_syn"
                | "interet_ass_syn_detail"
                | "interet_org_priv"
                | "interet_org_priv_detail"
                | "interet_pol_adm"
                | "interet_pol_adm_detail"
                | "langues"
                | "metier"
                | "metier_detail"
                | "secteurs_activite_detailles"
                | "secteurs_activite_detailles_detail"
                | "secteurs_activite_medias"
                | "secteurs_activite_medias_detail"
                | "secteurs_activite_rp"
                | "secteurs_activite_rp_detail"
                | "transformation_majeure"
                | "transformation_majeure_detail"
            ):
                value = profile.match_making.get(name)
            case "bw_trigger":
                value = [
                    BW_TRIGGER_LABEL.get(x, x) for x in profile.get_all_bw_trigger()
                ]
            case _:
                raise KeyError(f"cell_value() Inconsistent key: {name}")
        if isinstance(value, list):
            return self.list_to_str(value)
        return value

    def do_top_info(self) -> None:
        self.sheet["table"].extend(
            [
                {"row": ["AIPress24"], "style": "bold"},
                {
                    "row": [
                        {
                            "value": self.title,
                            "style": "bold",
                        }
                    ],
                    "style": "default_table_row",
                },
                {"row": [], "style": "default_table_row"},
                {
                    "row": [
                        {"value": "Date export:"},
                        {"value": self.date_now.isoformat(" ", "minutes")},
                    ],
                    "style": "default_table_row",
                },
                {"row": [], "style": "default_table_row"},
            ]
        )

    def do_header_line(self) -> None:
        row = [
            {
                "style": "bold_left_bg_gray_grid_06pt",
                "value": self.columns_definition[name].header,
            }
            for name in self.columns
        ]
        self.sheet["table"].append({"row": row, "style": "default_table_row"})

    def fetch_data(self) -> list[User]:
        stmt = (
            select(User)
            .where(
                # all users, wether inscription validated or not :
                # User.active == false(),
                User.is_clone == false(),
                User.deleted_at.is_(None),
                User.submited_at >= self.start_date,
            )
            .order_by(nulls_last(desc(User.submited_at)))
        )
        return list(db.session.scalars(stmt))

    def user_row(self, user: User) -> dict[str, Any]:
        profile = user.profile
        row = [self.cell_value(user, profile, name) for name in self.columns]
        return {"row": row, "style": "default_table_row"}

    def do_content_lines(self) -> None:
        for user in self.fetch_data():
            self.sheet["table"].append(self.user_row(user))

    def do_columns_width(self) -> None:
        self.sheet["width"] = [
            self.columns_definition[name].width for name in self.columns
        ]

    def make_sheet(self) -> None:
        self.do_start_date()
        self.init_columns_definition()
        self.do_top_info()
        self.do_header_line()
        self.do_content_lines()
        self.do_columns_width()


class ExporterModifications(ExporterInscriptions):
    sheet_name = "Modifications"
    columns = [
        "submited_at",
        "validated_at",
        "validation_status",
        "bw_trigger",
        "profile_label",
        "last_name",
        "first_name",
        "gender",
        "pseudo",
        "no_carte_presse",
        "email",
        "tel_mobile",
        "macaron_repas",
        "macaron_verre",
        "presentation",
        "organisation_name",
        "competences",
        "competences_journalisme",
        "experiences",
        "formations",
        "langues",
        "metier",
        "metier_detail",
    ]

    @property
    def title(self) -> str:
        dt = self.start_date.strftime("%d/%m/%Y")
        return f"Modification importantes depuis le {dt}"

    @property
    def filename(self) -> str:
        return f"modifications_depuis_{self.start_date.strftime('%Y-%m-%d')}.ods"

    def fetch_data(self) -> list[User]:
        stmt = (
            select(User)
            .where(
                User.active == true(),
                User.is_clone == false(),
                User.deleted_at.is_(None),
                User.modified_at >= self.start_date,
                User.validation_status != LABEL_INSCRIPTION_VALIDEE,
            )
            .order_by(nulls_last(desc(User.modified_at)))
        )
        return list(db.session.scalars(stmt))


class ExporterUsers(ExporterInscriptions):
    sheet_name = "Utilisateurs"
    columns = [
        "submited_at",
        "validated_at",
        "last_login_at",
        "bw_trigger",
        "profile_label",
        "last_name",
        "first_name",
        "gender",
        "pseudo",
        "id",
        "roles",
        "no_carte_presse",
        "email",
        "tel_mobile",
        "macaron_repas",
        "macaron_verre",
        "macaron_hebergement",
        "presentation",
        "organisation_name",
        "competences",
        "competences_journalisme",
        "experiences",
        "formations",
        "langues",
        "metier",
        "metier_detail",
    ]

    @property
    def title(self) -> str:
        return "Utilisateurs"

    @property
    def filename(self) -> str:
        return f"utilisateurs_{self.start_date.strftime('%Y-%m-%d')}.ods"

    def fetch_data(self) -> list[User]:
        stmt = (
            select(User)
            .where(
                User.active == true(),
                User.is_clone == false(),
                User.deleted_at.is_(None),
            )
            .order_by(nulls_last(User.last_name))
        )
        return list(db.session.scalars(stmt))


@blueprint.route("/export_inscription")
def export_inscription_route():
    generator = ExporterInscriptions()
    generator.run()
    stream = BytesIO(generator.document)
    stream.seek(0)
    return send_file(
        stream,
        mimetype="application/vnd.oasis.opendocument.spreadsheet",
        download_name=generator.filename,
        as_attachment=True,
    )


@blueprint.route("/export_modification")
def export_modification_route():
    generator = ExporterModifications()
    generator.run()
    stream = BytesIO(generator.document)
    stream.seek(0)
    return send_file(
        stream,
        mimetype="application/vnd.oasis.opendocument.spreadsheet",
        download_name=generator.filename,
        as_attachment=True,
    )


@blueprint.route("/export_users")
def export_users_route():
    generator = ExporterUsers()
    generator.run()
    stream = BytesIO(generator.document)
    stream.seek(0)
    return send_file(
        stream,
        mimetype="application/vnd.oasis.opendocument.spreadsheet",
        download_name=generator.filename,
        as_attachment=True,
    )
