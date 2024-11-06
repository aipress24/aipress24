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
from app.flask.lib.pages import page
from app.modules.kyc.dynform import (
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

    def context(self) -> dict[str, Any]:
        allow_editing = (
            self.org
            and self.org.type != OrganisationTypeEnum.AUTO
            and self.user.is_manager
        )

        return {
            "org": self.org,
            "org_name": self.org.name if self.org else "",
            "org_bw_type": self.org.bw_type if self.org else "",
            "allow_editing": allow_editing,
            "is_manager": self.user.is_manager,
            "is_leader": self.user.is_leader,
            "render_field": render_field,
            "form": self.generate_form() if self.org else FlaskForm(),
        }

    def post(self) -> str | Response:
        results = request.form.to_dict(flat=True)
        import sys

        print("////", results, file=sys.stderr)
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
        return TestForm(obj=self.org)


def string_field(name="", description="", mandatory: bool = False) -> Field:
    survey_field = SurveyField(
        id=name, name=name, type="string", description=description
    )
    mandatory_code = "M" if mandatory else ""
    return custom_string_field(survey_field, mandatory_code)


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


# broken
# @with_appcontext
# def list_field(
#     name="", description="", mandatory: bool = False, ontology_map: str = ""
# ) -> Field:
#     survey_field = SurveyField(id=name, name=name, type="url", description=description)
#     mandatory_code = "M" if mandatory else ""
#     return custom_list_field(survey_field, mandatory_code, ontology_map)


class TestForm(FlaskForm):
    name = string_field("name", "Nom de l'organisation", True)
    siren = string_field("siren", "Numéro SIREN", True)
    tva = string_field("tva", "Numéro de TVA intracommunataire", True)
    description = textarea_field("description", "Description", True)
    tel_standard = tel_field("tel_standard", "Téléphone (standard)", True)
    # taille_orga = list_field(
    # "taille_orga", "Taille organisation (effectif)", True, "list_taille_orga"
    # )

    leader_name = string_field("leader_name", "Nom du dirigeant", True)
    leader_coords = textarea_field("leader_name", "Coordonées du dirigeant", True)
    payer_name = string_field("payer_name", "Nom du payeur", True)
    payer_coords = textarea_field("payer_coords", "Coordonées du payeur", True)

    domain = string_field("domain", "Domaine", False)
    site_url = string_field("site_url", "URL du site (web)", False)
    jobs_url = string_field("jobs_url", "URL du site (emplois)", False)
    github_url = string_field("github_url", "URL du site (github)", False)
    linkedin_url = string_field("linkedin_url", "URL du site (linkedin)", False)
    logo_url = string_field("logo_url", "URL du logo de l'organisation", False)
    cover_image_url = string_field(
        "cover_image_url", "URL de l'image de présentation", False
    )
