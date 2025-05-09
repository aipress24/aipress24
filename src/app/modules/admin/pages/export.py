# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from collections import namedtuple
from datetime import datetime, timedelta
from io import BytesIO
from typing import Any
from zoneinfo import ZoneInfo

import pytz
from arrow import Arrow
from flask import send_file
from odsgenerator import odsgenerator
from sqlalchemy import desc, false, nulls_last, select, true

from app.constants import BW_TRIGGER_LABEL, LABEL_INSCRIPTION_VALIDEE, LOCAL_TZ
from app.enums import OrganisationTypeEnum
from app.flask.extensions import db
from app.flask.lib.pages import Page, page
from app.models.auth import KYCProfile, User
from app.models.organisation import Organisation
from app.modules.admin import blueprint

from .home import AdminHomePage

FieldColumn = namedtuple("FieldColumn", "name header width")  # noqa: PYI024

LOCALTZ = pytz.timezone(LOCAL_TZ)


def as_naive_localtz(value: datetime) -> datetime:
    return value.astimezone(LOCALTZ).replace(tzinfo=None)


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
        self.date_now = datetime.now(tz=ZoneInfo(LOCAL_TZ))
        start = self.date_now - timedelta(days=31)
        self.start_date = start.replace(hour=0, minute=0, second=0, microsecond=0)

    def init_columns_definition(self) -> None:
        text3 = "3cm"
        text4 = "4cm"
        text5 = "5cm"
        text6 = "6cm"
        text8 = "8cm"
        text12 = "12cm"
        short = "1.5cm"
        small = "2cm"
        fields = [
            FieldColumn("adresse_pro", "Adresse", text5),
            FieldColumn("bw_trigger", "BW validé", text5),
            FieldColumn("competences", "Compétences", text8),
            FieldColumn("competences_journalisme", "Compétences journalisme", text8),
            FieldColumn("compl_adresse_pro", "Adresse complem.", text5),
            FieldColumn("dirigeant", "Dirigeant", short),
            FieldColumn("email", "Email", text6),
            FieldColumn("email_secours", "Email secours", text6),
            FieldColumn("experiences", "Expériences", text12),
            FieldColumn("first_name", "Prénom", text4),
            FieldColumn("formations", "Formations", text12),
            FieldColumn("gender", "Civilité", short),
            FieldColumn("hobbies", "Hobbies", text12),
            FieldColumn("id", "ID", short),
            FieldColumn("interet_ass_syn", "Intérêt asso/syndic.", text8),
            FieldColumn("interet_ass_syn_detail", "Intérêt asso/syndic. détail", text8),
            FieldColumn("interet_org_priv", "Intérêt org. privées", text8),
            FieldColumn(
                "interet_org_priv_detail", "Intérêt org. privées détail", text8
            ),
            FieldColumn("interet_pol_adm", "Intérêt politique/adm.", text8),
            FieldColumn(
                "interet_pol_adm_detail", "Intérêt politique/adm. détail", text8
            ),
            FieldColumn("karma", "Réputation", small),
            FieldColumn("langues", "Langues", text8),
            FieldColumn("last_login_at", "Dernière connect.", text3),
            FieldColumn("last_name", "Nom", text4),
            FieldColumn("login_count", "Nb connect.", text3),
            FieldColumn("macaron_hebergement", "Hébergement", small),
            FieldColumn("macaron_repas", "Repas", small),
            FieldColumn("macaron_verre", "Verre", small),
            FieldColumn("manager", "Manager", short),
            FieldColumn("metier", "Métier", text8),
            FieldColumn("metier_detail", "Métier détail", text8),
            FieldColumn("no_carte_presse", "Carte Presse", text3),
            FieldColumn("organisation_name", "Organisation", text5),
            FieldColumn("pays_zip_ville", "Pays", small),
            FieldColumn("pays_zip_ville_detail", "Ville", text5),
            FieldColumn("presentation", "Présentation", text12),
            FieldColumn("profile_label", "Profil", text12),
            FieldColumn("pseudo", "Pseudo", text3),
            FieldColumn("roles", "Rôles", text3),
            FieldColumn("secteurs_activite_detailles", "Secteur activité", text8),
            FieldColumn(
                "secteurs_activite_detailles_detail", "Secteur activité détail", text8
            ),
            FieldColumn("secteurs_activite_medias", "Secteur activité médias", text8),
            FieldColumn(
                "secteurs_activite_medias_detail",
                "Secteur activité médias détail",
                text8,
            ),
            FieldColumn("secteurs_activite_rp", "Secteur activité PR", text8),
            FieldColumn(
                "secteurs_activite_rp_detail", "Secteur activité PR détail", text8
            ),
            FieldColumn("status", "Statut", text3),
            FieldColumn("submited_at", "Inscription", text3),
            FieldColumn("taille_orga", "Taille orga.", text3),
            FieldColumn("tel_mobile", "Mobile", text3),
            FieldColumn("tel_standard", "Tél standard", text3),
            FieldColumn("transformation_majeure", "Transformation majeure", text8),
            FieldColumn(
                "transformation_majeure_detail", "Transformation majeure détail", text8
            ),
            FieldColumn("type_agence_rp", "Type PR agency", text5),
            FieldColumn("type_entreprise_media", "Type entrepr. média", text5),
            FieldColumn("type_orga", "Type organisation", text5),
            FieldColumn("type_orga_detail", "Type organisation détail", text5),
            FieldColumn("type_presse_et_media", "Type presse & média", text5),
            FieldColumn("url_site_web", "URL web", text5),
            FieldColumn("validated_at", "Validation", text3),
            FieldColumn("validation_status", "Validation statut", text4),
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
            case "dirigeant":
                value = user.is_leader
            case "manager":
                value = user.is_manager
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
                msg = f"cell_value() Inconsistent key: {name}"
                raise KeyError(msg)
        if isinstance(value, list):
            return self.list_to_str(value)
        if isinstance(value, datetime):
            value = as_naive_localtz(value)
        return value

    def do_top_info(self) -> None:
        self.sheet["table"].extend(
            [
                {"row": ["Aipress24"], "style": "bold"},
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
        "validation_status",
        "last_login_at",
        "login_count",
        "bw_trigger",
        "profile_label",
        "last_name",
        "first_name",
        "gender",
        "id",
        "email",
        "email_secours",
        "roles",
        "pseudo",
        "no_carte_presse",
        "email",
        "tel_mobile",
        "macaron_repas",
        "macaron_verre",
        "macaron_hebergement",
        "status",
        "karma",
        "presentation",
        "organisation_name",
        "dirigeant",
        "manager",
        "pays_zip_ville",
        "pays_zip_ville_detail",
        "adresse_pro",
        "compl_adresse_pro",
        "compl_adresse_pro",
        "tel_standard",
        "type_agence_rp",
        "type_entreprise_media",
        "type_orga",
        "type_orga_detail",
        "type_presse_et_media",
        "url_site_web",
        "competences",
        "competences_journalisme",
        "experiences",
        "formations",
        "hobbies",
        "langues",
        "metier",
        "metier_detail",
        "interet_ass_syn",
        "interet_ass_syn_detail",
        "interet_org_priv",
        "interet_org_priv_detail",
        "interet_pol_adm",
        "interet_pol_adm_detail",
        "secteurs_activite_detailles",
        "secteurs_activite_detailles_detail",
        "secteurs_activite_medias",
        "secteurs_activite_medias_detail",
        "secteurs_activite_rp",
        "secteurs_activite_rp_detail",
        "transformation_majeure",
        "transformation_majeure_detail",
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


class ExporterOrganisations:
    sheet_name = "Organisations"
    columns = [
        "id",
        "created_at",
        "modified_at",
        "name",
        "type",
        "siren",
        "tva",
        "tel_standard",
        "taille_orga",
        "description",
        "metiers",
        "status",
        "karma",
        "nb_members",
        "agree_cppap",
        "membre_sapi",
        "membre_satev",
        "membre_saphir",
        "site_url",
        "logo_url",
        "cover_image_url",
        "members",
        "managers",
        "leaders",
    ]

    def __init__(self) -> None:
        self.date_now: datetime = None  # type: ignore
        self.document: bytes = b""
        self.columns_definition: dict[str, FieldColumn] = {}
        self.sheet = {"name": self.sheet_name, "table": []}

    @property
    def title(self) -> str:
        dt = self.date_now.strftime("%d/%m/%Y")
        return f"Organisations à ala date: {dt}"

    @property
    def filename(self) -> str:
        return f"organisation_{self.date_now.strftime('%Y-%m-%d')}.ods"

    def run(self) -> None:
        self.date_now = datetime.now(tz=ZoneInfo(LOCAL_TZ))
        self.make_sheet()
        content = {"body": [self.sheet]}
        self.document = odsgenerator.ods_bytes(content)

    def init_columns_definition(self) -> None:
        text3 = "3cm"
        text4 = "4cm"
        # text5 = "5cm"
        # text6 = "6cm"
        text8 = "8cm"
        text12 = "12cm"
        short = "1.4cm"
        small = "2cm"
        fields = [
            FieldColumn("id", "ID", text3),
            FieldColumn("created_at", "Création", text3),
            FieldColumn("leaders", "Dirigeants", text12),
            FieldColumn("modified_at", "Modification", text3),
            FieldColumn("name", "Nom", text4),
            FieldColumn("slug", "Slug", text4),
            FieldColumn("type", "Type", text4),
            FieldColumn("siren", "SIREN", text3),
            FieldColumn("tva", "TVA", text4),
            FieldColumn("tel_standard", "Tél standard", text3),
            FieldColumn("taille_orga", "Taille orga.", text3),
            FieldColumn("description", "Description", text8),
            FieldColumn("managers", "Managers", text12),
            FieldColumn("members", "Membres", text12),
            FieldColumn("metiers", "Métiers", text8),
            FieldColumn("status", "Statut", text8),
            FieldColumn("karma", "Réputation", small),
            FieldColumn("site_url", "URL site", text4),
            FieldColumn("logo_url", "URL logo", text4),
            FieldColumn("cover_image_url", "URL cover", text4),
            FieldColumn("nb_members", "Nb membres", small),
            FieldColumn("agree_cppap", "CPPAP", short),
            FieldColumn("membre_sapi", "SAPI", short),
            FieldColumn("membre_satev", "SATEV", short),
            FieldColumn("membre_saphir", "SAPHIR", short),
        ]
        self.columns_definition = {f.name: f for f in fields}

    @staticmethod
    def list_to_str(list_or_str: list | str | Any) -> str:
        if isinstance(list_or_str, list):
            return ", ".join(str(x) for x in list_or_str)
        return str(list_or_str)

    def cell_value(
        self,
        org: Organisation,
        name: str,
    ) -> str | datetime | int | bool:
        match name:
            case (
                "name"
                | "slug"
                | "type"
                | "siren"
                | "tva"
                | "tel_standard"
                | "taille_orga"
                | "description"
                | "metiers"
                | "status"
                | "karma"
                | "site_url"
                | "logo_url"
                | "cover_image_url"
                | "agree_cppap"
                | "membre_sapi"
                | "membre_satev"
                | "membre_saphir"
            ):
                value = getattr(org, name)
            case "members":
                value = ", ".join(u.email for u in org.members)
            case "managers":
                value = ", ".join(u.email for u in org.managers)
            case "leaders":
                value = ", ".join(u.email for u in org.leaders)
            case "id":
                value = str(org.id)
            case "created_at":
                value = org.created_at
                if isinstance(value, Arrow):
                    value = value.datetime
            case "validated_at":
                value = org.validated_at
                if isinstance(value, Arrow):
                    value = value.datetime
            case "modified_at":
                value = org.modified_at
                if isinstance(value, Arrow):
                    value = value.datetime
            case "nb_members":
                value = len(org.members)
            case _:
                msg = f"cell_value() Inconsistent key: {name}"
                raise KeyError(msg)
        if isinstance(value, list):
            return self.list_to_str(value)
        if isinstance(value, datetime):
            value = as_naive_localtz(value)
        return value

    def do_top_info(self) -> None:
        self.sheet["table"].extend(
            [
                {"row": ["Aaipress24"], "style": "bold"},
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
            select(Organisation)
            .where(
                Organisation.type != OrganisationTypeEnum.AUTO,
            )
            .order_by(nulls_last(Organisation.name))
        )
        return list(db.session.scalars(stmt))

    def orga_row(self, org: Organisation) -> dict[str, Any]:
        row = [self.cell_value(org, name) for name in self.columns]
        return {"row": row, "style": "default_table_row"}

    def do_content_lines(self) -> None:
        for org in self.fetch_data():
            self.sheet["table"].append(self.orga_row(org))

    def do_columns_width(self) -> None:
        self.sheet["width"] = [
            self.columns_definition[name].width for name in self.columns
        ]

    def make_sheet(self) -> None:
        self.init_columns_definition()
        self.do_top_info()
        self.do_header_line()
        self.do_content_lines()
        self.do_columns_width()


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


@blueprint.route("/export_organisations")
def export_organisations_route():
    generator = ExporterOrganisations()
    generator.run()
    stream = BytesIO(generator.document)
    stream.seek(0)
    return send_file(
        stream,
        mimetype="application/vnd.oasis.opendocument.spreadsheet",
        download_name=generator.filename,
        as_attachment=True,
    )
