# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Export functionality for admin views."""

from __future__ import annotations

from collections import namedtuple
from datetime import datetime, timedelta
from io import BytesIO
from typing import Any, ClassVar, cast
from zoneinfo import ZoneInfo

import pytz
from arrow import Arrow
from flask import abort, send_file
from odsgenerator import odsgenerator
from sqlalchemy import desc, false, nulls_last, select, true

from app.constants import BW_TRIGGER_LABEL, LABEL_INSCRIPTION_VALIDEE, LOCAL_TZ
from app.enums import OrganisationTypeEnum
from app.flask.extensions import db
from app.models.auth import KYCProfile, User
from app.models.organisation import Organisation
from app.modules.admin import blueprint

LOCALTZ = pytz.timezone(LOCAL_TZ)


@blueprint.route("/export/<exporter_name>")
def export_route(exporter_name: str):
    """Generic export route that handles all export types."""
    exporter_class = EXPORTERS.get(exporter_name)
    if exporter_class is None:
        abort(404)

    assert exporter_class is not None  # type narrowing for type checker
    generator = exporter_class()
    generator.run()
    stream = BytesIO(generator.document)
    stream.seek(0)
    return send_file(
        stream,
        mimetype="application/vnd.oasis.opendocument.spreadsheet",
        download_name=generator.filename,
        as_attachment=True,
    )


#
# Exporters
#

FieldColumn = namedtuple("FieldColumn", "name header width")  # noqa: PYI024


class BaseExporter:
    """Base class for all ODS exporters with shared functionality."""

    sheet_name: str = ""
    columns: ClassVar[list] = []

    # Common column width constants
    WIDTH_SHORT = "1.4cm"
    WIDTH_SMALL = "2cm"
    WIDTH_TEXT3 = "3cm"
    WIDTH_TEXT4 = "4cm"
    WIDTH_TEXT5 = "5cm"
    WIDTH_TEXT6 = "6cm"
    WIDTH_TEXT8 = "8cm"
    WIDTH_TEXT12 = "12cm"

    def __init__(self) -> None:
        self.date_now: datetime | None = None
        self.document: bytes = b""
        self.columns_definition: dict[str, FieldColumn] = {}
        self.sheet: dict[str, Any] = {"name": self.sheet_name, "table": []}

    @property
    def title(self) -> str:
        """Override in subclass to provide export title."""
        raise NotImplementedError

    @property
    def filename(self) -> str:
        """Override in subclass to provide export filename."""
        raise NotImplementedError

    def run(self) -> None:
        """Generate the ODS document."""
        self.make_sheet()
        content = {"body": [self.sheet]}
        self.document = odsgenerator.ods_bytes(content)

    @staticmethod
    def list_to_str(list_or_str: list | str | Any) -> str:
        """Convert list to comma-separated string."""
        match list_or_str:
            case list():
                return ", ".join(str(x) for x in list_or_str)
            case _:
                return str(list_or_str)

    @staticmethod
    def get_datetime_attr(obj: Any, name: str) -> datetime | None:
        """Get datetime attribute and convert from Arrow if needed."""
        value = getattr(obj, name)
        match value:
            case Arrow():
                return value.datetime
            case _:
                return value

    def do_top_info(self) -> None:
        """Add header information to the sheet."""
        self.sheet["table"].extend(
            [
                {"row": ["AiPRESS24"], "style": "bold"},
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
                        {
                            "value": self.date_now.isoformat(" ", "minutes")
                            if self.date_now
                            else ""
                        },
                    ],
                    "style": "default_table_row",
                },
                {"row": [], "style": "default_table_row"},
            ]
        )

    def do_header_line(self) -> None:
        """Add column headers to the sheet."""
        row = [
            {
                "style": "bold_left_bg_gray_grid_06pt",
                "value": self.columns_definition[name].header,
            }
            for name in self.columns
        ]
        self.sheet["table"].append({"row": row, "style": "default_table_row"})

    def do_columns_width(self) -> None:
        """Set column widths for the sheet."""
        self.sheet["width"] = [
            self.columns_definition[name].width for name in self.columns
        ]

    def init_columns_definition(self) -> None:
        """Override in subclass to define columns."""
        raise NotImplementedError

    def fetch_data(self) -> list[Any]:
        """Override in subclass to fetch data to export."""
        raise NotImplementedError

    def do_content_lines(self) -> None:
        """Override in subclass to add content rows."""
        raise NotImplementedError

    def make_sheet(self) -> None:
        """Build the complete sheet. Override if needed."""
        self.init_columns_definition()
        self.do_top_info()
        self.do_header_line()
        self.do_content_lines()
        self.do_columns_width()


class InscriptionsExporter(BaseExporter):
    sheet_name = "Inscriptions"
    columns: ClassVar[list] = [
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
        "metier_principal",
        "metier_principal_detail",
        "metier",
        "metier_detail",
        "organisation_name",
        "competences",
        "competences_journalisme",
        "presentation",
        "langues",
        "formations",
        "experiences",
        "macaron_hebergement",
        "macaron_repas",
        "macaron_verre",
    ]

    def __init__(self) -> None:
        super().__init__()
        self.start_date: datetime | None = None

    @property
    def title(self) -> str:
        assert self.start_date is not None
        dt = self.start_date.strftime("%d/%m/%Y")
        return f"Demandes d'inscriptions depuis le {dt}"

    @property
    def filename(self) -> str:
        assert self.start_date is not None
        return f"inscriptions_depuis_{self.start_date.strftime('%Y-%m-%d')}.ods"

    def do_start_date(self) -> None:
        self.date_now = datetime.now(tz=ZoneInfo(LOCAL_TZ))
        start = self.date_now - timedelta(days=31)
        self.start_date = start.replace(hour=0, minute=0, second=0, microsecond=0)

    def init_columns_definition(self) -> None:
        # Use base class width constants
        text3 = self.WIDTH_TEXT3
        text4 = self.WIDTH_TEXT4
        text5 = self.WIDTH_TEXT5
        text6 = self.WIDTH_TEXT6
        text8 = self.WIDTH_TEXT8
        text12 = self.WIDTH_TEXT12
        short = "1.5cm"  # Custom width for this exporter
        small = self.WIDTH_SMALL
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
            FieldColumn("metier_principal", "Métier principal", text8),
            FieldColumn("metier_principal_detail", "Métier p. détail", text8),
            FieldColumn("metier", "Métier secondaire", text8),
            FieldColumn("metier_detail", "Métier s. détail", text8),
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
            FieldColumn("email_relation_presse", "Email rel presse", text6),
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

    # Field name to data source mapping
    _USER_ATTRS = {
        "id",
        "validation_status",
        "last_login_at",
        "login_count",
        "gcu_acceptation",
        "gcu_acceptation_date",
        "last_name",
        "first_name",
        "gender",
        "email",
        "email_secours",
        "tel_mobile",
        "status",
        "karma",
        "organisation_name",
    }
    _PROFILE_ATTRS = {"profile_label", "presentation"}
    _INFO_PERSONNELLE_ATTRS = {
        "pseudo",
        "no_carte_presse",
        "metier_principal",
        "metier_principal_detail",
        "metier",
        "metier_detail",
        "competences",
        "competences_journalisme",
        "langues",
        "formations",
        "experiences",
    }
    _INFO_PRO_ATTRS = {
        "nom_groupe_presse",
        "nom_media",
        "nom_media_instit",
        "type_entreprise_media",
        "type_presse_et_media",
        "nom_group_com",
        "nom_agence_rp",
        "type_agence_rp",
        "nom_adm",
        "nom_orga",
        "type_orga",
        "type_orga_detail",
        "taille_orga",
        "secteurs_activite_medias",
        "secteurs_activite_medias_detail",
        "secteurs_activite_rp",
        "secteurs_activite_rp_detail",
        "secteurs_activite_detailles",
        "secteurs_activite_detailles_detail",
        "pays_zip_ville",
        "pays_zip_ville_detail",
        "adresse_pro",
        "compl_adresse_pro",
        "email_relation_presse",
        "tel_standard",
        "ligne_directe",
        "url_site_web",
    }
    _MATCH_MAKING_ATTRS = {
        "fonctions_journalisme",
        "fonctions_pol_adm",
        "fonctions_pol_adm_detail",
        "fonctions_org_priv",
        "fonctions_org_priv_detail",
        "fonctions_ass_syn",
        "fonctions_ass_syn_detail",
        "interet_pol_adm",
        "interet_pol_adm_detail",
        "interet_org_priv",
        "interet_org_priv_detail",
        "interet_ass_syn",
        "interet_ass_syn_detail",
        "transformation_majeure",
        "transformation_majeure_detail",
    }
    _INFO_HOBBY_ATTRS = {
        "hobbies",
        "macaron_hebergement",
        "macaron_repas",
        "macaron_verre",
    }

    def cell_value(
        self,
        user: User,
        profile: KYCProfile,
        name: str,
    ) -> str | datetime | int | bool | None:
        value = self._get_cell_value_raw(user, profile, name)

        match value:
            case list():
                return self.list_to_str(value)
            case datetime():
                return as_naive_localtz(value)
            case _:
                return cast(str | int | bool | None, value)

    def _get_cell_value_raw(self, user: User, profile: KYCProfile, name: str):
        """Get raw cell value before formatting."""
        # Handle special cases first
        match name:
            case "dirigeant":
                return user.is_leader
            case "manager":
                return user.is_manager
            case "submited_at" | "validated_at" | "modified_at":
                return self.get_datetime_attr(user, name)
            case "roles":
                return [x.name for x in getattr(user, name)]
            case "bw_trigger":
                return [
                    BW_TRIGGER_LABEL.get(x, x) for x in profile.get_all_bw_trigger()
                ]
            case _:
                # Handle grouped attributes via lookup
                return self._get_grouped_attr(user, profile, name)

    def _get_grouped_attr(self, user: User, profile: KYCProfile, name: str):
        """Get value from grouped attributes."""
        match name:
            case _ if name in self._USER_ATTRS:
                return getattr(user, name)
            case _ if name in self._PROFILE_ATTRS:
                return getattr(profile, name)
            case _ if name in self._INFO_PERSONNELLE_ATTRS:
                return profile.info_personnelle.get(name)
            case _ if name in self._INFO_PRO_ATTRS:
                return profile.info_professionnelle.get(name)
            case _ if name in self._MATCH_MAKING_ATTRS:
                return profile.match_making.get(name)
            case _ if name in self._INFO_HOBBY_ATTRS:
                return profile.info_hobby.get(name)
            case _:
                msg = f"cell_value() non managed key: {name!r}"
                raise KeyError(msg)

    def fetch_data(self) -> list[User]:
        stmt = (
            select(User)
            .where(
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

    def make_sheet(self) -> None:
        """Override to add start_date initialization before building sheet."""
        self.do_start_date()
        super().make_sheet()


class ModificationsExporter(InscriptionsExporter):
    sheet_name = "Modifications"
    columns: ClassVar[list] = [
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
        "metier_principal",
        "metier_principal_detail",
        "metier",
        "metier_detail",
        "organisation_name",
        "competences",
        "competences_journalisme",
        "presentation",
        "langues",
        "formations",
        "experiences",
        "macaron_hebergement",
        "macaron_repas",
        "macaron_verre",
    ]

    @property
    def title(self) -> str:
        assert self.start_date is not None
        dt = self.start_date.strftime("%d/%m/%Y")
        return f"Modification importantes depuis le {dt}"

    @property
    def filename(self) -> str:
        assert self.start_date is not None
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


class UsersExporter(InscriptionsExporter):
    sheet_name = "Utilisateurs"
    columns: ClassVar[list] = [
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
        "tel_mobile",
        "status",
        "karma",
        "metier_principal",
        "metier_principal_detail",
        "metier",
        "metier_detail",
        "organisation_name",
        "dirigeant",
        "manager",
        "pays_zip_ville",
        "pays_zip_ville_detail",
        "adresse_pro",
        "compl_adresse_pro",
        "compl_adresse_pro",
        "email_relation_presse",
        "tel_standard",
        "type_agence_rp",
        "type_entreprise_media",
        "type_orga",
        "type_orga_detail",
        "type_presse_et_media",
        "url_site_web",
        "competences",
        "competences_journalisme",
        "presentation",
        "langues",
        "formations",
        "experiences",
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
        "hobbies",
        "macaron_hebergement",
        "macaron_repas",
        "macaron_verre",
    ]

    @property
    def title(self) -> str:
        return "Utilisateurs"

    @property
    def filename(self) -> str:
        assert self.date_now is not None
        return f"utilisateurs_{self.date_now.strftime('%Y-%m-%d')}.ods"

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


class OrganisationsExporter(BaseExporter):
    sheet_name = "Organisations"
    columns: ClassVar[list] = [
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
        "members",
        "managers",
        "leaders",
    ]

    @property
    def title(self) -> str:
        assert self.date_now is not None
        dt = self.date_now.strftime("%d/%m/%Y")
        return f"Organisations à la date: {dt}"

    @property
    def filename(self) -> str:
        assert self.date_now is not None
        return f"organisation_{self.date_now.strftime('%Y-%m-%d')}.ods"

    def init_columns_definition(self) -> None:
        # Use base class width constants
        text3 = self.WIDTH_TEXT3
        text4 = self.WIDTH_TEXT4
        text8 = self.WIDTH_TEXT8
        text12 = self.WIDTH_TEXT12
        short = self.WIDTH_SHORT
        small = self.WIDTH_SMALL
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
            FieldColumn("nb_members", "Nb membres", small),
            FieldColumn("agree_cppap", "CPPAP", short),
            FieldColumn("membre_sapi", "SAPI", short),
            FieldColumn("membre_satev", "SATEV", short),
            FieldColumn("membre_saphir", "SAPHIR", short),
        ]
        self.columns_definition = {f.name: f for f in fields}

    # Organization attribute names that are directly accessible
    _ORG_ATTRS = {
        "name",
        "slug",
        "type",
        "siren",
        "tva",
        "tel_standard",
        "taille_orga",
        "description",
        "metiers",
        "status",
        "karma",
        "site_url",
        "logo_url",
        "cover_image_url",
        "agree_cppap",
        "membre_sapi",
        "membre_satev",
        "membre_saphir",
    }

    def cell_value(
        self,
        org: Organisation,
        name: str,
    ) -> str | datetime | int | bool | None:
        # Handle special cases
        value: str | datetime | int | bool | list | None
        match name:
            case "members":
                value = ", ".join(u.email for u in org.members)
            case "managers":
                value = ", ".join(u.email for u in org.managers)
            case "leaders":
                value = ", ".join(u.email for u in org.leaders)
            case "id":
                value = str(org.id)
            case "created_at" | "validated_at" | "modified_at":
                value = self.get_datetime_attr(org, name)
            case "nb_members":
                value = len(org.members)
            case _ if name in self._ORG_ATTRS:
                # Handle direct attributes
                value = getattr(org, name)
            case _:
                msg = f"cell_value() Inconsistent key: {name}"
                raise KeyError(msg)

        # Format and return value
        match value:
            case list():
                return self.list_to_str(value)
            case datetime():
                return as_naive_localtz(value)
            case _:
                return value

    def fetch_data(self) -> list[Organisation]:
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

    def make_sheet(self) -> None:
        """Override to initialize date_now before building sheet."""
        self.date_now = datetime.now(tz=ZoneInfo(LOCAL_TZ))
        super().make_sheet()


# Mapping of exporter names to exporter classes
EXPORTERS = {
    "inscription": InscriptionsExporter,
    "modification": ModificationsExporter,
    "users": UsersExporter,
    "organisations": OrganisationsExporter,
}


def as_naive_localtz(value: datetime) -> datetime:
    return value.astimezone(LOCALTZ).replace(tzinfo=None)
