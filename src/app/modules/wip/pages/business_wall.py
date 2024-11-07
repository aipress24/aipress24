# Copyright (c) 2021-2024 - Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from typing import Any

from flask import g, request
from flask_wtf import FlaskForm
from werkzeug import Response
from wtforms import Field

from app.enums import BWTypeEnum, OrganisationTypeEnum
from app.flask.extensions import db
from app.flask.lib.pages import page
from app.modules.kyc.dynform import (
    custom_bool_field,
    custom_dual_multi_field,
    custom_list_field,
    custom_multi_field,
    custom_string_field,
    custom_tel_field,
    custom_textarea_field,
    custom_url_field,
)
from app.modules.kyc.renderer import render_field
from app.modules.kyc.survey_dataclass import SurveyField

from .base import BaseWipPage
from .home import HomePage

__all__ = ["BusinessWallPage"]


@page
class BusinessWallPage(BaseWipPage):
    name = "org-profile"
    label = "Business Wall"
    title = "Gérer ma page institutionnelle"
    icon = "building-library"

    # path = "/org-page"
    template = "wip/pages/institutional-page.j2"
    parent = HomePage

    def __init__(self):
        self.user = g.user
        self.org = self.user.organisation  # Organisation or None
        self.form = None

    def context(self) -> dict[str, Any]:
        allow_editing = (
            self.org
            and self.org.type != OrganisationTypeEnum.AUTO
            and self.user.is_manager
        )
        self.form = self.generate_form() if self.org else FlaskForm()

        return {
            "org": self.org,
            "org_name": self.org.name if self.org else "",
            "org_bw_type": self.org.bw_type if self.org else "",
            "allow_editing": allow_editing,
            "is_manager": self.user.is_manager,
            "is_leader": self.user.is_leader,
            "render_field": render_field,
            "form": self.form,
        }

    def post(self) -> str | Response:
        results = request.form.to_dict(flat=False)
        self.merge_form(results)
        return self.render()

    def generate_form(self) -> tuple[FlaskForm, list[str]]:
        """The form contains several Fields and sub titles information.

            (group1.label, [fieldname_1 fieldname_2, ...]),
        ]
        """
        match self.org.bw_type:
            case None:
                return self.form_none()
            case BWTypeEnum.AGENCY:
                return self.form_agency()
            case BWTypeEnum.MEDIA:
                return self.form_media()
            case BWTypeEnum.CORPORATE:
                return self.form_corporate()
            case BWTypeEnum.PRESSUNION:
                return self.form_pressunion()
            case BWTypeEnum.COM:
                return self.form_com()
            case BWTypeEnum.ORGANISATION:
                return self.form_organisation()
            case BWTypeEnum.TRANSFORMER:
                return self.form_transformer()
            case BWTypeEnum.ACADEMICS:
                return self.form_academics()
            case _:
                raise ValueError('Unknown organisation bw_type "{self.org.bw_type}"')

    def form_none(self) -> FlaskForm:
        """Empty form (actually unused by the template)."""
        return FlaskForm, []

    def form_agency(self) -> FlaskForm:
        return self.test_form()

    def form_media(self) -> FlaskForm:
        return self.test_form()

    def form_corporate(self) -> FlaskForm:
        return self.test_form()

    def form_pressunion(self) -> FlaskForm:
        return self.test_form()

    def form_com(self) -> FlaskForm:
        return self.test_form()

    def form_organisation(self) -> FlaskForm:
        return self.test_form()

    def form_transformer(self) -> FlaskForm:
        return self.test_form()

    def form_academics(self) -> FlaskForm:
        return self.test_form()

    def test_form(self) -> FlaskForm:
        return self.generate_dynamic_form()

    def generate_dynamic_form(self) -> FlaskForm:
        class BWDynForm(FlaskForm):
            pass

        BWDynForm.name = string_field("name", "Nom de l'organisation", True)
        BWDynForm.media_name = string_field(
            "media_name", "Nom officiel du titre", False
        )
        BWDynForm.siren = string_field("siren", "Numéro SIREN", True)
        BWDynForm.tva = string_field("tva", "Numéro de TVA intracommunataire", True)
        BWDynForm.leader_name = string_field("leader_name", "Nom du dirigeant", True)
        BWDynForm.leader_coords = textarea_field(
            "leader_coords", "Coordonées du dirigeant", True
        )
        BWDynForm.payer_name = string_field("payer_name", "Nom du payeur", True)
        BWDynForm.payer_coords = textarea_field(
            "payer_coords", "Coordonées du payeur", True
        )

        BWDynForm.description = textarea_field("description", "Description", True)
        BWDynForm.tel_standard = tel_field("tel_standard", "Téléphone (standard)", True)
        BWDynForm.taille_orga = list_field(
            "taille_orga", "Taille organisation (effectif)", True, "list_taille_orga"
        )
        BWDynForm.type_entreprise_media = multi_field(
            "type_entreprise_media",
            "Types d’entreprise de presse",
            False,
            "multi_type_entreprise_medias",
        )
        BWDynForm.metiers_presse = multi_field(
            "metiers_presse",
            "Métiers de la presse",
            False,
            "multi_fonctions_journalisme",
        )
        BWDynForm.metiers = dual_multi_field(
            "metiers",
            "Le cas échéant, quels autres métiers exercez-vous ?; Métiers",
            True,
            "multidual_metiers",
        )

        BWDynForm.secteurs_activite = dual_multi_field(
            "secteurs_activite",
            "Secteurs d’activité dans lequel exerce votre organisation; Sous secteurs",
            True,
            "multidual_secteurs_detail",
        )
        BWDynForm.secteurs_activite_couverts = dual_multi_field(
            "secteurs_activite_couverts",
            "Secteurs d’activité couverts par votre organisation; Sous secteurs",
            True,
            "multidual_secteurs_detail",
        )
        BWDynForm.type_organisation = dual_multi_field(
            "type_organisation",
            "Type d'organisation; Détail",
            True,
            "multidual_type_orga",
        )
        BWDynForm.main_events = textarea_field(
            "main_events", "Principaux Events organisés", False
        )
        BWDynForm.main_customers = textarea_field(
            "main_customers", "Principales références clients", False
        )
        BWDynForm.main_prizes = textarea_field(
            "main_prizes", "Prix et autres distinctions", False
        )
        BWDynForm.positionnement_editorial = textarea_field(
            "positionnement_editorial", "Positionnement éditorial", False
        )
        BWDynForm.audience_cible = textarea_field(
            "audience_cible", "Audiences ciblées", False
        )
        BWDynForm.tirage = string_field("tirage", "Tirage", False)
        BWDynForm.frequence_publication = string_field(
            "frequence_publication", "Fréquence de publication", False
        )

        BWDynForm.agree_arcom = bool_field("agree_arcom", "Agréé ARCOM", False)
        BWDynForm.agree_cppap = bool_field("agree_cppap", "Agréé CPPAP", False)
        BWDynForm.number_cppap = string_field("number_cppap", "Numéro CPPAP", False)
        BWDynForm.membre_sapi = bool_field("membre_sapi", "Membre du SAPI", False)
        BWDynForm.membre_satev = bool_field("membre_satev", "Membre du SATEV", False)
        BWDynForm.membre_saphir = bool_field("membre_saphir", "Membre du SAPHIR", False)

        BWDynForm.domain = string_field("domain", "Domaine", False)
        BWDynForm.site_url = string_field("site_url", "URL du site (web)", False)
        BWDynForm.jobs_url = string_field("jobs_url", "URL du site (emplois)", False)
        BWDynForm.github_url = string_field("github_url", "URL du site (github)", False)
        BWDynForm.linkedin_url = string_field(
            "linkedin_url", "URL du site (linkedin)", False
        )
        BWDynForm.logo_url = string_field(
            "logo_url", "URL du logo de l'organisation", False
        )
        BWDynForm.cover_image_url = string_field(
            "cover_image_url", "URL de l'image de présentation", False
        )
        form = BWDynForm(obj=self.org)
        form.metiers.data2 = self.org.metiers_detail
        form.secteurs_activite.data2 = self.org.secteurs_activite_detail
        form.secteurs_activite_couverts.data2 = (
            self.org.secteurs_activite_couverts_detail
        )
        form.type_organisation.data2 = self.org.type_organisation_detail

        return form

    def merge_form(self, results: dict[str, Any]) -> None:
        # to adapt for the various BW types
        def _parse_bool(key: str) -> bool:
            content = results.get(key, [])
            if not content:
                return False
            return bool(content[0])

        org = self.org
        org.name = results["media_name"][0]
        org.media_name = results["media_name"][0]
        org.siren = results["siren"][0]
        org.tva = results["tva"][0]
        org.description = results["description"][0]
        org.tel_standard = results["tel_standard"][0]
        org.taille_orga = results["taille_orga"][0]
        org.type_entreprise_media = results["type_entreprise_media"]
        org.metiers = results["metiers"]
        org.metiers_detail = results["metiers_detail"]
        org.secteurs_activite = results["secteurs_activite"]
        org.secteurs_activite_detail = results["secteurs_activite_detail"]
        org.secteurs_activite_couverts = results["secteurs_activite_couverts"]
        org.secteurs_activite_couverts_detail = results[
            "secteurs_activite_couverts_detail"
        ]
        org.type_organisation = results["type_organisation"]
        org.type_organisation_detail = results["type_organisation_detail"]
        org.leader_name = results["leader_name"][0]
        org.leader_coords = results["leader_coords"][0]
        org.payer_name = results["payer_name"][0]
        org.payer_coords = results["payer_coords"][0]
        org.main_events = results["main_events"][0]
        org.main_customers = results["main_customers"][0]
        org.main_prizes = results["main_prizes"][0]
        org.positionnement_editorial = results["positionnement_editorial"][0]
        org.audience_cible = results["audience_cible"][0]
        org.tirage = results["tirage"][0]
        org.frequence_publication = results["frequence_publication"][0]
        org.metiers_presse = results["metiers_presse"]

        org.agree_arcom = _parse_bool("agree_arcom")
        org.agree_cppap = _parse_bool("agree_cppap")
        org.number_cppap = results["number_cppap"][0]
        org.membre_satev = _parse_bool("membre_satev")
        org.membre_saphir = _parse_bool("membre_saphir")
        org.domain = results["domain"][0]
        org.site_url = results["site_url"][0]
        org.jobs_url = results["jobs_url"][0]
        org.github_url = results["github_url"][0]
        org.linkedin_url = results["linkedin_url"][0]
        org.logo_url = results["logo_url"][0]
        org.cover_image_url = results["cover_image_url"][0]

        db_session = db.session
        db_session.merge(self.org)
        db_session.commit()


def string_field(name="", description="", mandatory: bool = False) -> Field:
    survey_field = SurveyField(
        id=name, name=name, type="string", description=description
    )
    mandatory_code = "M" if mandatory else ""
    return custom_string_field(survey_field, mandatory_code)


def bool_field(name="", description="", mandatory: bool = False) -> Field:
    survey_field = SurveyField(
        id=name, name=name, type="boolean", description=description
    )
    mandatory_code = "M" if mandatory else ""
    return custom_bool_field(survey_field, mandatory_code)


def textarea_field(name="", description="", mandatory: bool = False) -> Field:
    survey_field = SurveyField(
        id=name, name=name, type="textarea", description=description
    )
    mandatory_code = "M" if mandatory else ""
    return custom_textarea_field(survey_field, mandatory_code)


def tel_field(name="", description="", mandatory: bool = False) -> Field:
    survey_field = SurveyField(id=name, name=name, type="tel", description=description)
    mandatory_code = "M" if mandatory else ""
    return custom_tel_field(survey_field, mandatory_code)


def url_field(name="", description="", mandatory: bool = False) -> Field:
    survey_field = SurveyField(id=name, name=name, type="url", description=description)
    mandatory_code = "M" if mandatory else ""
    return custom_url_field(survey_field, mandatory_code)


def list_field(
    name="", description="", mandatory: bool = False, ontology_map: str = ""
) -> Field:
    survey_field = SurveyField(id=name, name=name, type="list", description=description)
    mandatory_code = "M" if mandatory else ""
    return custom_list_field(survey_field, mandatory_code, ontology_map)


def dual_multi_field(
    name="",
    description="",
    mandatory: bool = False,
    ontology_map: str = "",
) -> Field:
    survey_field = SurveyField(
        id=name, name=name, type="multidual", description=description
    )
    mandatory_code = "M" if mandatory else ""
    return custom_dual_multi_field(survey_field, mandatory_code, ontology_map)


def multi_field(
    name="",
    description="",
    mandatory: bool = False,
    ontology_map: str = "",
) -> Field:
    survey_field = SurveyField(
        id=name, name=name, type="multi", description=description
    )
    mandatory_code = "M" if mandatory else ""
    return custom_multi_field(survey_field, mandatory_code, ontology_map)
