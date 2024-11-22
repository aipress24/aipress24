# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from typing import Any

from flask import g, request
from flask_wtf import FlaskForm
from werkzeug import Response
from wtforms import Field

from app.enums import BWTypeEnum, ProfileEnum
from app.flask.extensions import db
from app.flask.lib.pages import page
from app.modules.admin.invitations import emails_invited_to_organisation
from app.modules.admin.org_email_utils import (
    change_invitations_emails,
    change_leaders_emails,
    change_managers_emails,
    change_members_emails,
)
from app.modules.kyc.dynform import (
    custom_bool_field,
    custom_country_field,
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
    title = "Gérer ma page institutionnelle"  # type: ignore
    icon = "building-library"

    # path = "/org-page"
    template = "wip/pages/institutional-page.j2"
    parent = HomePage

    def __init__(self):
        self.user = g.user
        self.org = self.user.organisation  # Organisation or None
        self.form = None
        self.readonly: bool = False

    def context(self) -> dict[str, Any]:
        has_bw_org = self.org and not self.org.is_auto_or_inactive
        allow_editing = has_bw_org and self.user.is_manager
        self.readonly = not allow_editing
        self.form = self.generate_form() if self.org else FlaskForm()
        if self.org:
            members = list(self.org.members)
        else:
            members = []
        return {
            "org": self.org,
            "org_name": self.org.name if self.org else "",
            "org_bw_type": self.org.bw_type if self.org else "",
            "has_bw_org": has_bw_org,
            "allow_editing": allow_editing,
            "is_manager": self.user.is_manager,
            "is_leader": self.user.is_leader,
            "members": members,
            "count_members": len(members),
            "managers": self.org.managers if self.org else [],
            "leaders": self.org.leaders if self.org else [],
            "invitations_emails": (
                emails_invited_to_organisation(self.org.id) if self.org else []
            ),
            "address_formatted": self.org.formatted_address if self.org else "",
            "render_field": render_field,
            "form": self.form,
        }

    def post(self) -> str | Response:
        """Non hx post.

        Used for submitting a form requiring in-page WTFom validation.
        """
        form = request.form
        if "change_bw_data" in form:
            results = form.to_dict(flat=False)
            self.merge_form(results)
            return self.render()

        action = request.form.get("action")
        match action:
            case "change_emails":
                raw_mails = request.form["content"]
                change_members_emails(self.org, raw_mails)
                response = Response("")
                response.headers["HX-Redirect"] = self.url
            case "change_managers_emails":
                raw_mails = request.form["content"]
                change_managers_emails(self.org, raw_mails, keep_one=True)
                response = Response("")
                response.headers["HX-Redirect"] = self.url
            case "change_leaders_emails":
                raw_mails = request.form["content"]
                change_leaders_emails(self.org, raw_mails)
                response = Response("")
                response.headers["HX-Redirect"] = self.url
            case "change_invitations_emails":
                raw_mails = request.form["content"]
                change_invitations_emails(self.org, raw_mails)
                response = Response("")
                response.headers["HX-Redirect"] = self.url
            # case "change_bw_data":
            #     results = request.form.to_dict(flat=False)
            #     self.merge_form(results)
            #     response = Response("")
            #     response.headers["HX-Redirect"] = self.url
            #     return response
            case "reload_bw_data":
                response = Response("")
                response.headers["HX-Redirect"] = self.url
                return response
            case _:
                response = Response("")
                response.headers["HX-Redirect"] = self.url
        return response

    def generate_form(self) -> FlaskForm:
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
                msg = 'Unknown organisation bw_type "{self.org.bw_type}"'
                raise ValueError(msg)

    def form_none(self) -> FlaskForm:
        """Empty form (actually unused by the template)."""
        return FlaskForm()

    def form_agency(self) -> FlaskForm:
        profile = self.user.profile
        profile_code = ProfileEnum[profile.profile_code]

        class BWDynForm(FlaskForm):
            pass

        BWDynForm.name = string_field(
            "name",
            description=(
                "Nom de l’agence de presse, du journal, du magazine, du média "
                "ou du SPEL, Syndicat de presse ou de médias, de l’association "
                "de journalistes, du club de la presse ou de l’école de "
                "journalisme"
            ),
            mandatory=True,
            readonly=self.readonly,
        )

        if profile_code in {
            ProfileEnum.PM_DIR,
            ProfileEnum.PM_JR_CP_SAL,
            ProfileEnum.PM_JR_PIG,
        }:
            BWDynForm.nom_groupe = string_field(
                "nom_groupe",
                "Nom du groupe de presse, d’édition ou de média",
                False,
                self.readonly,
            )

        BWDynForm.siren = string_field("siren", "Numéro SIREN", True, self.readonly)
        BWDynForm.tva = string_field(
            "tva", "Numéro de TVA intracommunataire", True, self.readonly
        )
        BWDynForm.leader_name = string_field(
            "leader_name", "Nom du dirigeant", True, self.readonly
        )
        BWDynForm.leader_coords = textarea_field(
            "leader_coords", "Coordonées du dirigeant", True, self.readonly
        )
        BWDynForm.payer_name = string_field(
            "payer_name", "Nom du payeur", True, self.readonly
        )
        BWDynForm.payer_coords = textarea_field(
            "payer_coords", "Coordonées du payeur", True, self.readonly
        )
        BWDynForm.description = textarea_field(
            "description", "Description", True, self.readonly
        )
        BWDynForm.tel_standard = tel_field(
            "tel_standard", "Téléphone (standard)", True, self.readonly
        )
        BWDynForm.pays_zip_ville = country_code_field(
            "pays_zip_ville",
            "Pays;Code postal et ville",
            False,
            ontology_map="country_pays",
            readonly=self.readonly,
        )
        BWDynForm.taille_orga = list_field(
            "taille_orga",
            "Taille organisation (effectif)",
            True,
            ontology_map="list_taille_orga",
            readonly=self.readonly,
        )

        # BWDynForm.type_organisation = dual_multi_field(
        #     "type_organisation",
        #     "Type d'organisation; Détail",
        #     True,
        #     "multidual_type_orga",
        #     self.readonly,
        # )

        BWDynForm.type_entreprise_media = multi_field(
            "type_entreprise_media",
            "Types d’entreprise de presse",
            True,
            "multi_type_entreprise_medias",
            readonly=self.readonly,
        )

        BWDynForm.type_presse_et_media = multi_field(
            "type_presse_et_media",
            "Types d’entreprise de presse",
            True,
            "multi_type_entreprise_medias",
            readonly=self.readonly,
        )

        BWDynForm.metiers_presse = multi_field(
            "metiers_presse",
            "Métiers de la presse",
            True,
            "multi_fonctions_journalisme",
            readonly=self.readonly,
        )
        BWDynForm.metiers = dual_multi_field(
            "metiers",
            "Le cas échéant, quels autres métiers exercez-vous ?; Métiers",
            False,
            "multidual_metiers",
            self.readonly,
        )

        BWDynForm.secteurs_activite_medias = dual_multi_field(
            "secteurs_activite_medias",
            "Secteurs d’activité couverts par votre organisation; Sous secteurs",
            True,
            "multidual_secteurs_detail",
            self.readonly,
        )

        BWDynForm.main_events = textarea_field(
            "main_events", "Principaux Events organisés", False, self.readonly
        )
        BWDynForm.main_customers = textarea_field(
            "main_customers", "Principales références clients", False, self.readonly
        )
        BWDynForm.main_prizes = textarea_field(
            "main_prizes", "Prix et autres distinctions", False, self.readonly
        )
        BWDynForm.positionnement_editorial = textarea_field(
            "positionnement_editorial", "Positionnement éditorial", False, self.readonly
        )
        BWDynForm.audience_cible = textarea_field(
            "audience_cible", "Audiences ciblées", False, self.readonly
        )
        BWDynForm.tirage = string_field("tirage", "Tirage", False, self.readonly)
        BWDynForm.frequence_publication = string_field(
            "frequence_publication", "Fréquence de publication", False, self.readonly
        )

        BWDynForm.agree_arcom = bool_field(
            "agree_arcom", "Agréé ARCOM", False, self.readonly
        )
        BWDynForm.agree_cppap = bool_field(
            "agree_cppap", "Agréé CPPAP", False, self.readonly
        )
        BWDynForm.number_cppap = string_field(
            "number_cppap", "Numéro CPPAP", False, self.readonly
        )
        BWDynForm.membre_sapi = bool_field(
            "membre_sapi", "Membre du SAPI", False, self.readonly
        )
        BWDynForm.membre_satev = bool_field(
            "membre_satev", "Membre du SATEV", False, self.readonly
        )
        BWDynForm.membre_saphir = bool_field(
            "membre_saphir", "Membre du SAPHIR", False, self.readonly
        )

        BWDynForm.domain = string_field("domain", "Domaine", False, self.readonly)
        BWDynForm.site_url = url_field(
            "site_url", "URL du site (web)", False, self.readonly
        )
        BWDynForm.jobs_url = url_field(
            "jobs_url", "URL du site (emplois)", False, self.readonly
        )
        BWDynForm.github_url = url_field(
            "github_url", "URL du site (github)", False, self.readonly
        )
        BWDynForm.linkedin_url = url_field(
            "linkedin_url", "URL du site (linkedin)", False, self.readonly
        )
        BWDynForm.logo_url = string_field(
            "logo_url", "URL du logo de l'organisation", False, self.readonly
        )
        BWDynForm.cover_image_url = url_field(
            "cover_image_url", "URL de l'image de présentation", False, self.readonly
        )

        form = BWDynForm(obj=self.org)
        form.pays_zip_ville.data2 = self.org.pays_zip_ville_detail
        form.metiers.data2 = self.org.metiers_detail
        form.secteurs_activite_medias.data2 = self.org.secteurs_activite_medias_detail
        # form.secteurs_activite_rp.data2 = self.org.secteurs_activite_rp_detail
        # form.secteurs_activite.data2 = self.org.secteurs_activite_detail
        # form.type_organisation.data2 = self.org.type_organisation_detail

        return form

    def form_media(self) -> FlaskForm:
        profile = self.user.profile
        profile_code = ProfileEnum[profile.profile_code]

        class BWDynForm(FlaskForm):
            pass

        BWDynForm.name = string_field(
            "name",
            description=(
                "Nom de l’agence de presse, du journal, du magazine, du média "
                "ou du SPEL, Syndicat de presse ou de médias, de l’association "
                "de journalistes, du club de la presse ou de l’école de "
                "journalisme"
            ),
            mandatory=True,
            readonly=self.readonly,
        )

        if profile_code in {
            ProfileEnum.PM_DIR,
            ProfileEnum.PM_JR_CP_SAL,
            ProfileEnum.PM_JR_PIG,
        }:
            BWDynForm.nom_groupe = string_field(
                "nom_groupe",
                "Nom du groupe de presse, d’édition ou de média",
                False,
                self.readonly,
            )

        BWDynForm.siren = string_field("siren", "Numéro SIREN", True, self.readonly)
        BWDynForm.tva = string_field(
            "tva", "Numéro de TVA intracommunataire", True, self.readonly
        )
        BWDynForm.leader_name = string_field(
            "leader_name", "Nom du dirigeant", True, self.readonly
        )
        BWDynForm.leader_coords = textarea_field(
            "leader_coords", "Coordonées du dirigeant", True, self.readonly
        )
        BWDynForm.payer_name = string_field(
            "payer_name", "Nom du payeur", True, self.readonly
        )
        BWDynForm.payer_coords = textarea_field(
            "payer_coords", "Coordonées du payeur", True, self.readonly
        )
        BWDynForm.description = textarea_field(
            "description", "Description", True, self.readonly
        )
        BWDynForm.tel_standard = tel_field(
            "tel_standard", "Téléphone (standard)", True, self.readonly
        )
        BWDynForm.pays_zip_ville = country_code_field(
            "pays_zip_ville",
            "Pays;Code postal et ville",
            False,
            ontology_map="country_pays",
            readonly=self.readonly,
        )
        BWDynForm.taille_orga = list_field(
            "taille_orga",
            "Taille organisation (effectif)",
            True,
            ontology_map="list_taille_orga",
            readonly=self.readonly,
        )

        # BWDynForm.type_organisation = dual_multi_field(
        #     "type_organisation",
        #     "Type d'organisation; Détail",
        #     True,
        #     "multidual_type_orga",
        #     self.readonly,
        # )

        BWDynForm.type_entreprise_media = multi_field(
            "type_entreprise_media",
            "Types d’entreprise de presse",
            True,
            "multi_type_entreprise_medias",
            readonly=self.readonly,
        )

        BWDynForm.type_presse_et_media = multi_field(
            "type_presse_et_media",
            "Types d’entreprise de presse",
            True,
            "multi_type_entreprise_medias",
            readonly=self.readonly,
        )

        BWDynForm.metiers_presse = multi_field(
            "metiers_presse",
            "Métiers de la presse",
            True,
            "multi_fonctions_journalisme",
            readonly=self.readonly,
        )
        BWDynForm.metiers = dual_multi_field(
            "metiers",
            "Le cas échéant, quels autres métiers exercez-vous ?; Métiers",
            False,
            "multidual_metiers",
            self.readonly,
        )

        BWDynForm.secteurs_activite_medias = dual_multi_field(
            "secteurs_activite_medias",
            "Secteurs d’activité couverts par votre organisation; Sous secteurs",
            True,
            "multidual_secteurs_detail",
            self.readonly,
        )

        BWDynForm.main_events = textarea_field(
            "main_events", "Principaux Events organisés", False, self.readonly
        )
        BWDynForm.main_customers = textarea_field(
            "main_customers", "Principales références clients", False, self.readonly
        )
        BWDynForm.main_prizes = textarea_field(
            "main_prizes", "Prix et autres distinctions", False, self.readonly
        )
        BWDynForm.positionnement_editorial = textarea_field(
            "positionnement_editorial", "Positionnement éditorial", False, self.readonly
        )
        BWDynForm.audience_cible = textarea_field(
            "audience_cible", "Audiences ciblées", False, self.readonly
        )
        BWDynForm.tirage = string_field("tirage", "Tirage", False, self.readonly)
        BWDynForm.frequence_publication = string_field(
            "frequence_publication", "Fréquence de publication", False, self.readonly
        )

        BWDynForm.agree_arcom = bool_field(
            "agree_arcom", "Agréé ARCOM", False, self.readonly
        )
        BWDynForm.agree_cppap = bool_field(
            "agree_cppap", "Agréé CPPAP", False, self.readonly
        )
        BWDynForm.number_cppap = string_field(
            "number_cppap", "Numéro CPPAP", False, self.readonly
        )
        BWDynForm.membre_sapi = bool_field(
            "membre_sapi", "Membre du SAPI", False, self.readonly
        )
        BWDynForm.membre_satev = bool_field(
            "membre_satev", "Membre du SATEV", False, self.readonly
        )
        BWDynForm.membre_saphir = bool_field(
            "membre_saphir", "Membre du SAPHIR", False, self.readonly
        )

        BWDynForm.domain = string_field("domain", "Domaine", False, self.readonly)
        BWDynForm.site_url = url_field(
            "site_url", "URL du site (web)", False, self.readonly
        )
        BWDynForm.jobs_url = url_field(
            "jobs_url", "URL du site (emplois)", False, self.readonly
        )
        BWDynForm.github_url = url_field(
            "github_url", "URL du site (github)", False, self.readonly
        )
        BWDynForm.linkedin_url = url_field(
            "linkedin_url", "URL du site (linkedin)", False, self.readonly
        )
        BWDynForm.logo_url = string_field(
            "logo_url", "URL du logo de l'organisation", False, self.readonly
        )
        BWDynForm.cover_image_url = url_field(
            "cover_image_url", "URL de l'image de présentation", False, self.readonly
        )

        form = BWDynForm(obj=self.org)
        form.pays_zip_ville.data2 = self.org.pays_zip_ville_detail
        form.metiers.data2 = self.org.metiers_detail
        form.secteurs_activite_medias.data2 = self.org.secteurs_activite_medias_detail
        # form.secteurs_activite_rp.data2 = self.org.secteurs_activite_rp_detail
        # form.secteurs_activite.data2 = self.org.secteurs_activite_detail
        # form.type_organisation.data2 = self.org.type_organisation_detail

        return form

    def form_corporate(self) -> FlaskForm:
        profile = self.user.profile
        profile_code = ProfileEnum[profile.profile_code]

        class BWDynForm(FlaskForm):
            pass

        BWDynForm.name = string_field(
            "name",
            description=("Nom du média institutionnel"),
            mandatory=True,
            readonly=self.readonly,
        )

        if profile_code in {
            ProfileEnum.PM_DIR,
            ProfileEnum.PM_JR_CP_SAL,
            ProfileEnum.PM_JR_PIG,
        }:
            BWDynForm.nom_groupe = string_field(
                "nom_groupe",
                "Nom du groupe de presse, d’édition ou de média",
                False,
                self.readonly,
            )

        BWDynForm.siren = string_field("siren", "Numéro SIREN", True, self.readonly)
        BWDynForm.tva = string_field(
            "tva", "Numéro de TVA intracommunataire", True, self.readonly
        )
        BWDynForm.leader_name = string_field(
            "leader_name", "Nom du dirigeant", True, self.readonly
        )
        BWDynForm.leader_coords = textarea_field(
            "leader_coords", "Coordonées du dirigeant", True, self.readonly
        )
        BWDynForm.payer_name = string_field(
            "payer_name", "Nom du payeur", True, self.readonly
        )
        BWDynForm.payer_coords = textarea_field(
            "payer_coords", "Coordonées du payeur", True, self.readonly
        )
        BWDynForm.description = textarea_field(
            "description", "Description", True, self.readonly
        )
        BWDynForm.tel_standard = tel_field(
            "tel_standard", "Téléphone (standard)", True, self.readonly
        )
        BWDynForm.pays_zip_ville = country_code_field(
            "pays_zip_ville",
            "Pays;Code postal et ville",
            False,
            ontology_map="country_pays",
            readonly=self.readonly,
        )
        BWDynForm.taille_orga = list_field(
            "taille_orga",
            "Taille organisation (effectif)",
            True,
            ontology_map="list_taille_orga",
            readonly=self.readonly,
        )

        # BWDynForm.type_organisation = dual_multi_field(
        #     "type_organisation",
        #     "Type d'organisation; Détail",
        #     True,
        #     "multidual_type_orga",
        #     self.readonly,
        # )

        # BWDynForm.type_entreprise_media = multi_field(
        #     "type_entreprise_media",
        #     "Types d’entreprise de presse",
        #     True,
        #     "multi_type_entreprise_medias",
        #     readonly=self.readonly,
        # )

        BWDynForm.type_presse_et_media = multi_field(
            "type_presse_et_media",
            "Types d’entreprise de presse",
            True,
            "multi_type_entreprise_medias",
            readonly=self.readonly,
        )

        BWDynForm.metiers_presse = multi_field(
            "metiers_presse",
            "Métiers de la presse",
            True,
            "multi_fonctions_journalisme",
            readonly=self.readonly,
        )
        BWDynForm.metiers = dual_multi_field(
            "metiers",
            "Le cas échéant, quels autres métiers exercez-vous ?; Métiers",
            False,
            "multidual_metiers",
            self.readonly,
        )

        # BWDynForm.secteurs_activite_medias = dual_multi_field(
        #     "secteurs_activite_medias",
        #     "Secteurs d’activité couverts par votre organisation; Sous secteurs",
        #     True,
        #     "multidual_secteurs_detail",
        #     self.readonly,
        # )

        BWDynForm.main_events = textarea_field(
            "main_events", "Principaux Events organisés", False, self.readonly
        )
        BWDynForm.main_customers = textarea_field(
            "main_customers", "Principales références clients", False, self.readonly
        )
        BWDynForm.main_prizes = textarea_field(
            "main_prizes", "Prix et autres distinctions", False, self.readonly
        )
        BWDynForm.positionnement_editorial = textarea_field(
            "positionnement_editorial", "Positionnement éditorial", False, self.readonly
        )
        BWDynForm.audience_cible = textarea_field(
            "audience_cible", "Audiences ciblées", False, self.readonly
        )
        BWDynForm.tirage = string_field("tirage", "Tirage", False, self.readonly)
        BWDynForm.frequence_publication = string_field(
            "frequence_publication", "Fréquence de publication", False, self.readonly
        )

        BWDynForm.agree_arcom = bool_field(
            "agree_arcom", "Agréé ARCOM", False, self.readonly
        )
        BWDynForm.agree_cppap = bool_field(
            "agree_cppap", "Agréé CPPAP", False, self.readonly
        )
        BWDynForm.number_cppap = string_field(
            "number_cppap", "Numéro CPPAP", False, self.readonly
        )
        BWDynForm.membre_sapi = bool_field(
            "membre_sapi", "Membre du SAPI", False, self.readonly
        )
        BWDynForm.membre_satev = bool_field(
            "membre_satev", "Membre du SATEV", False, self.readonly
        )
        BWDynForm.membre_saphir = bool_field(
            "membre_saphir", "Membre du SAPHIR", False, self.readonly
        )

        BWDynForm.domain = string_field("domain", "Domaine", False, self.readonly)
        BWDynForm.site_url = url_field(
            "site_url", "URL du site (web)", False, self.readonly
        )
        BWDynForm.jobs_url = url_field(
            "jobs_url", "URL du site (emplois)", False, self.readonly
        )
        BWDynForm.github_url = url_field(
            "github_url", "URL du site (github)", False, self.readonly
        )
        BWDynForm.linkedin_url = url_field(
            "linkedin_url", "URL du site (linkedin)", False, self.readonly
        )
        BWDynForm.logo_url = string_field(
            "logo_url", "URL du logo de l'organisation", False, self.readonly
        )
        BWDynForm.cover_image_url = url_field(
            "cover_image_url", "URL de l'image de présentation", False, self.readonly
        )

        form = BWDynForm(obj=self.org)
        form.pays_zip_ville.data2 = self.org.pays_zip_ville_detail
        form.metiers.data2 = self.org.metiers_detail
        # form.secteurs_activite_medias.data2 = self.org.secteurs_activite_medias_detail
        # form.secteurs_activite_rp.data2 = self.org.secteurs_activite_rp_detail
        # form.secteurs_activite.data2 = self.org.secteurs_activite_detail
        # form.type_organisation.data2 = self.org.type_organisation_detail

        return form

    def form_pressunion(self) -> FlaskForm:
        # profile = self.user.profile
        # profile_code = ProfileEnum[profile.profile_code]

        class BWDynForm(FlaskForm):
            pass

        BWDynForm.name = string_field(
            "name",
            description=(
                "Nom de l’agence de presse, du journal, du magazine, du média "
                "ou du SPEL, Syndicat de presse ou de médias, de l’association "
                "de journalistes, du club de la presse ou de l’école de "
                "journalisme"
            ),
            mandatory=True,
            readonly=self.readonly,
        )

        BWDynForm.siren = string_field("siren", "Numéro SIREN", True, self.readonly)
        BWDynForm.tva = string_field(
            "tva", "Numéro de TVA intracommunataire", True, self.readonly
        )
        BWDynForm.leader_name = string_field(
            "leader_name", "Nom du dirigeant", True, self.readonly
        )
        BWDynForm.leader_coords = textarea_field(
            "leader_coords", "Coordonées du dirigeant", True, self.readonly
        )
        BWDynForm.payer_name = string_field(
            "payer_name", "Nom du payeur", True, self.readonly
        )
        BWDynForm.payer_coords = textarea_field(
            "payer_coords", "Coordonées du payeur", True, self.readonly
        )
        BWDynForm.description = textarea_field(
            "description", "Description", True, self.readonly
        )
        BWDynForm.tel_standard = tel_field(
            "tel_standard", "Téléphone (standard)", True, self.readonly
        )
        BWDynForm.pays_zip_ville = country_code_field(
            "pays_zip_ville",
            "Pays;Code postal et ville",
            False,
            ontology_map="country_pays",
            readonly=self.readonly,
        )
        BWDynForm.taille_orga = list_field(
            "taille_orga",
            "Taille organisation (effectif)",
            True,
            ontology_map="list_taille_orga",
            readonly=self.readonly,
        )

        # BWDynForm.type_organisation = dual_multi_field(
        #     "type_organisation",
        #     "Type d'organisation; Détail",
        #     True,
        #     "multidual_type_orga",
        #     self.readonly,
        # )

        # BWDynForm.type_entreprise_media = multi_field(
        #     "type_entreprise_media",
        #     "Types d’entreprise de presse",
        #     True,
        #     "multi_type_entreprise_medias",
        #     readonly=self.readonly,
        # )

        # BWDynForm.type_presse_et_media = multi_field(
        #     "type_presse_et_media",
        #     "Types d’entreprise de presse",
        #     True,
        #     "multi_type_entreprise_medias",
        #     readonly=self.readonly,
        # )

        BWDynForm.metiers_presse = multi_field(
            "metiers_presse",
            "Métiers de la presse",
            True,
            "multi_fonctions_journalisme",
            readonly=self.readonly,
        )
        BWDynForm.metiers = dual_multi_field(
            "metiers",
            "Le cas échéant, quels autres métiers exercez-vous ?; Métiers",
            False,
            "multidual_metiers",
            self.readonly,
        )

        BWDynForm.secteurs_activite_medias = dual_multi_field(
            "secteurs_activite_medias",
            "Secteurs d’activité couverts par votre organisation; Sous secteurs",
            True,
            "multidual_secteurs_detail",
            self.readonly,
        )

        BWDynForm.main_events = textarea_field(
            "main_events", "Principaux Events organisés", False, self.readonly
        )
        BWDynForm.main_customers = textarea_field(
            "main_customers", "Principales références clients", False, self.readonly
        )
        BWDynForm.main_prizes = textarea_field(
            "main_prizes", "Prix et autres distinctions", False, self.readonly
        )
        BWDynForm.positionnement_editorial = textarea_field(
            "positionnement_editorial", "Positionnement éditorial", False, self.readonly
        )
        BWDynForm.audience_cible = textarea_field(
            "audience_cible", "Audiences ciblées", False, self.readonly
        )
        BWDynForm.tirage = string_field("tirage", "Tirage", False, self.readonly)
        BWDynForm.frequence_publication = string_field(
            "frequence_publication", "Fréquence de publication", False, self.readonly
        )

        BWDynForm.agree_arcom = bool_field(
            "agree_arcom", "Agréé ARCOM", False, self.readonly
        )
        BWDynForm.agree_cppap = bool_field(
            "agree_cppap", "Agréé CPPAP", False, self.readonly
        )
        BWDynForm.number_cppap = string_field(
            "number_cppap", "Numéro CPPAP", False, self.readonly
        )
        BWDynForm.membre_sapi = bool_field(
            "membre_sapi", "Membre du SAPI", False, self.readonly
        )
        BWDynForm.membre_satev = bool_field(
            "membre_satev", "Membre du SATEV", False, self.readonly
        )
        BWDynForm.membre_saphir = bool_field(
            "membre_saphir", "Membre du SAPHIR", False, self.readonly
        )

        BWDynForm.domain = string_field("domain", "Domaine", False, self.readonly)
        BWDynForm.site_url = url_field(
            "site_url", "URL du site (web)", False, self.readonly
        )
        BWDynForm.jobs_url = url_field(
            "jobs_url", "URL du site (emplois)", False, self.readonly
        )
        BWDynForm.github_url = url_field(
            "github_url", "URL du site (github)", False, self.readonly
        )
        BWDynForm.linkedin_url = url_field(
            "linkedin_url", "URL du site (linkedin)", False, self.readonly
        )
        BWDynForm.logo_url = string_field(
            "logo_url", "URL du logo de l'organisation", False, self.readonly
        )
        BWDynForm.cover_image_url = url_field(
            "cover_image_url", "URL de l'image de présentation", False, self.readonly
        )

        form = BWDynForm(obj=self.org)
        form.pays_zip_ville.data2 = self.org.pays_zip_ville_detail
        form.metiers.data2 = self.org.metiers_detail
        form.secteurs_activite_medias.data2 = self.org.secteurs_activite_medias_detail
        # form.secteurs_activite_rp.data2 = self.org.secteurs_activite_rp_detail
        # form.secteurs_activite.data2 = self.org.secteurs_activite_detail
        # form.type_organisation.data2 = self.org.type_organisation_detail

        return form

    def form_com(self) -> FlaskForm:
        profile = self.user.profile
        profile_code = ProfileEnum[profile.profile_code]

        class BWDynForm(FlaskForm):
            pass

        BWDynForm.name = string_field(
            "name",
            description=("Nom de la PR agency ou de l’agence de communicationl"),
            mandatory=True,
            readonly=self.readonly,
        )

        if profile_code in {
            ProfileEnum.PR_DIR,
            ProfileEnum.PR_CS,
        }:
            BWDynForm.nom_groupe = string_field(
                "nom_groupe",
                "Nom du groupe de relations presse ou de communication",
                False,
                self.readonly,
            )

        BWDynForm.siren = string_field("siren", "Numéro SIREN", True, self.readonly)
        BWDynForm.tva = string_field(
            "tva", "Numéro de TVA intracommunataire", True, self.readonly
        )
        BWDynForm.leader_name = string_field(
            "leader_name", "Nom du dirigeant", True, self.readonly
        )
        BWDynForm.leader_coords = textarea_field(
            "leader_coords", "Coordonées du dirigeant", True, self.readonly
        )
        BWDynForm.payer_name = string_field(
            "payer_name", "Nom du payeur", True, self.readonly
        )
        BWDynForm.payer_coords = textarea_field(
            "payer_coords", "Coordonées du payeur", True, self.readonly
        )
        BWDynForm.description = textarea_field(
            "description", "Description", True, self.readonly
        )
        BWDynForm.tel_standard = tel_field(
            "tel_standard", "Téléphone (standard)", True, self.readonly
        )
        BWDynForm.pays_zip_ville = country_code_field(
            "pays_zip_ville",
            "Pays;Code postal et ville",
            False,
            ontology_map="country_pays",
            readonly=self.readonly,
        )
        BWDynForm.taille_orga = list_field(
            "taille_orga",
            "Taille organisation (effectif)",
            True,
            ontology_map="list_taille_orga",
            readonly=self.readonly,
        )

        # BWDynForm.type_organisation = dual_multi_field(
        #     "type_organisation",
        #     "Type d'organisation; Détail",
        #     True,
        #     "multidual_type_orga",
        #     self.readonly,
        # )

        # BWDynForm.type_entreprise_media = multi_field(
        #     "type_entreprise_media",
        #     "Types d’entreprise de presse",
        #     True,
        #     "multi_type_entreprise_medias",
        #     readonly=self.readonly,
        # )

        BWDynForm.type_agence_rp = multi_field(
            "type_agence_rp",
            "Type de PR agency",
            True,
            "multi_type_agences_rp",
            readonly=self.readonly,
        )

        BWDynForm.metiers_presse = multi_field(
            "metiers_presse",
            "Métiers de la presse",
            True,
            "multi_fonctions_journalisme",
            readonly=self.readonly,
        )
        BWDynForm.metiers = dual_multi_field(
            "metiers",
            "Le cas échéant, quels autres métiers exercez-vous ?; Métiers",
            False,
            "multidual_metiers",
            self.readonly,
        )

        BWDynForm.secteurs_activite_rp = dual_multi_field(
            "secteurs_activite_rp",
            "Secteurs d’activité couverts par votre PR agency; Sous secteurs",
            True,
            "multidual_secteurs_detail",
            self.readonly,
        )

        BWDynForm.main_events = textarea_field(
            "main_events", "Principaux Events organisés", False, self.readonly
        )
        BWDynForm.main_customers = textarea_field(
            "main_customers", "Principales références clients", False, self.readonly
        )
        BWDynForm.main_prizes = textarea_field(
            "main_prizes", "Prix et autres distinctions", False, self.readonly
        )
        BWDynForm.positionnement_editorial = textarea_field(
            "positionnement_editorial", "Positionnement éditorial", False, self.readonly
        )
        BWDynForm.audience_cible = textarea_field(
            "audience_cible", "Audiences ciblées", False, self.readonly
        )
        BWDynForm.tirage = string_field("tirage", "Tirage", False, self.readonly)
        BWDynForm.frequence_publication = string_field(
            "frequence_publication", "Fréquence de publication", False, self.readonly
        )

        BWDynForm.agree_arcom = bool_field(
            "agree_arcom", "Agréé ARCOM", False, self.readonly
        )
        BWDynForm.agree_cppap = bool_field(
            "agree_cppap", "Agréé CPPAP", False, self.readonly
        )
        BWDynForm.number_cppap = string_field(
            "number_cppap", "Numéro CPPAP", False, self.readonly
        )
        BWDynForm.membre_sapi = bool_field(
            "membre_sapi", "Membre du SAPI", False, self.readonly
        )
        BWDynForm.membre_satev = bool_field(
            "membre_satev", "Membre du SATEV", False, self.readonly
        )
        BWDynForm.membre_saphir = bool_field(
            "membre_saphir", "Membre du SAPHIR", False, self.readonly
        )

        BWDynForm.domain = string_field("domain", "Domaine", False, self.readonly)
        BWDynForm.site_url = url_field(
            "site_url", "URL du site (web)", False, self.readonly
        )
        BWDynForm.jobs_url = url_field(
            "jobs_url", "URL du site (emplois)", False, self.readonly
        )
        BWDynForm.github_url = url_field(
            "github_url", "URL du site (github)", False, self.readonly
        )
        BWDynForm.linkedin_url = url_field(
            "linkedin_url", "URL du site (linkedin)", False, self.readonly
        )
        BWDynForm.logo_url = string_field(
            "logo_url", "URL du logo de l'organisation", False, self.readonly
        )
        BWDynForm.cover_image_url = url_field(
            "cover_image_url", "URL de l'image de présentation", False, self.readonly
        )

        form = BWDynForm(obj=self.org)
        form.pays_zip_ville.data2 = self.org.pays_zip_ville_detail
        form.metiers.data2 = self.org.metiers_detail
        # form.secteurs_activite_medias.data2 = self.org.secteurs_activite_medias_detail
        form.secteurs_activite_rp.data2 = self.org.secteurs_activite_rp_detail
        # form.secteurs_activite.data2 = self.org.secteurs_activite_detail
        # form.type_organisation.data2 = self.org.type_organisation_detail

        return form

    def form_organisation(self) -> FlaskForm:
        profile = self.user.profile
        profile_code = ProfileEnum[profile.profile_code]

        class BWDynForm(FlaskForm):
            pass

        BWDynForm.name = string_field(
            "name",
            description=("Nom de l’organisation"),
            mandatory=True,
            readonly=self.readonly,
        )

        if profile_code not in {
            ProfileEnum.XP_IND,
            ProfileEnum.XP_DIR_SU,
        }:
            BWDynForm.nom_groupe = string_field(
                "nom_groupe",
                "Nom du groupe, ministère, de l’administration publique ou de la fédération",
                False,
                self.readonly,
            )

        BWDynForm.siren = string_field("siren", "Numéro SIREN", True, self.readonly)
        BWDynForm.tva = string_field(
            "tva", "Numéro de TVA intracommunataire", True, self.readonly
        )
        BWDynForm.leader_name = string_field(
            "leader_name", "Nom du dirigeant", True, self.readonly
        )
        BWDynForm.leader_coords = textarea_field(
            "leader_coords", "Coordonées du dirigeant", True, self.readonly
        )
        BWDynForm.payer_name = string_field(
            "payer_name", "Nom du payeur", True, self.readonly
        )
        BWDynForm.payer_coords = textarea_field(
            "payer_coords", "Coordonées du payeur", True, self.readonly
        )
        BWDynForm.description = textarea_field(
            "description", "Description", True, self.readonly
        )
        BWDynForm.tel_standard = tel_field(
            "tel_standard", "Téléphone (standard)", True, self.readonly
        )
        BWDynForm.pays_zip_ville = country_code_field(
            "pays_zip_ville",
            "Pays;Code postal et ville",
            False,
            ontology_map="country_pays",
            readonly=self.readonly,
        )
        BWDynForm.taille_orga = list_field(
            "taille_orga",
            "Taille organisation (effectif)",
            True,
            ontology_map="list_taille_orga",
            readonly=self.readonly,
        )

        BWDynForm.type_organisation = dual_multi_field(
            "type_organisation",
            "Type d'organisation; Détail",
            True,
            "multidual_type_orga",
            self.readonly,
        )

        # BWDynForm.type_entreprise_media = multi_field(
        #     "type_entreprise_media",
        #     "Types d’entreprise de presse",
        #     True,
        #     "multi_type_entreprise_medias",
        #     readonly=self.readonly,
        # )

        # BWDynForm.type_agence_rp = multi_field(
        #     "type_agence_rp",
        #     "Type de PR agency",
        #     True,
        #     "multi_type_agences_rp",
        #     readonly=self.readonly,
        # )

        BWDynForm.metiers_presse = multi_field(
            "metiers_presse",
            "Métiers de la presse",
            True,
            "multi_fonctions_journalisme",
            readonly=self.readonly,
        )
        BWDynForm.metiers = dual_multi_field(
            "metiers",
            "Le cas échéant, quels autres métiers exercez-vous ?; Métiers",
            False,
            "multidual_metiers",
            self.readonly,
        )
        if profile_code in {
            ProfileEnum.PR_DIR_COM,
            ProfileEnum.PR_CS_COM,
        }:
            BWDynForm.secteurs_activite_rp = dual_multi_field(
                "secteurs_activite_rp",
                "Secteurs d’activité couverts par votre PR agency; Sous secteurs",
                True,
                "multidual_secteurs_detail",
                self.readonly,
            )

        BWDynForm.secteurs_activite = dual_multi_field(
            "secteurs_activite",
            "Secteurs d’activité dans lequel exerce votre organisation; Sous secteurs",
            True,
            "multidual_secteurs_detail",
            self.readonly,
        )

        BWDynForm.main_events = textarea_field(
            "main_events", "Principaux Events organisés", False, self.readonly
        )
        BWDynForm.main_customers = textarea_field(
            "main_customers", "Principales références clients", False, self.readonly
        )
        BWDynForm.main_prizes = textarea_field(
            "main_prizes", "Prix et autres distinctions", False, self.readonly
        )
        BWDynForm.positionnement_editorial = textarea_field(
            "positionnement_editorial", "Positionnement éditorial", False, self.readonly
        )
        BWDynForm.audience_cible = textarea_field(
            "audience_cible", "Audiences ciblées", False, self.readonly
        )
        BWDynForm.tirage = string_field("tirage", "Tirage", False, self.readonly)
        BWDynForm.frequence_publication = string_field(
            "frequence_publication", "Fréquence de publication", False, self.readonly
        )

        BWDynForm.agree_arcom = bool_field(
            "agree_arcom", "Agréé ARCOM", False, self.readonly
        )
        BWDynForm.agree_cppap = bool_field(
            "agree_cppap", "Agréé CPPAP", False, self.readonly
        )
        BWDynForm.number_cppap = string_field(
            "number_cppap", "Numéro CPPAP", False, self.readonly
        )
        BWDynForm.membre_sapi = bool_field(
            "membre_sapi", "Membre du SAPI", False, self.readonly
        )
        BWDynForm.membre_satev = bool_field(
            "membre_satev", "Membre du SATEV", False, self.readonly
        )
        BWDynForm.membre_saphir = bool_field(
            "membre_saphir", "Membre du SAPHIR", False, self.readonly
        )

        BWDynForm.domain = string_field("domain", "Domaine", False, self.readonly)
        BWDynForm.site_url = url_field(
            "site_url", "URL du site (web)", False, self.readonly
        )
        BWDynForm.jobs_url = url_field(
            "jobs_url", "URL du site (emplois)", False, self.readonly
        )
        BWDynForm.github_url = url_field(
            "github_url", "URL du site (github)", False, self.readonly
        )
        BWDynForm.linkedin_url = url_field(
            "linkedin_url", "URL du site (linkedin)", False, self.readonly
        )
        BWDynForm.logo_url = string_field(
            "logo_url", "URL du logo de l'organisation", False, self.readonly
        )
        BWDynForm.cover_image_url = url_field(
            "cover_image_url", "URL de l'image de présentation", False, self.readonly
        )

        form = BWDynForm(obj=self.org)
        form.pays_zip_ville.data2 = self.org.pays_zip_ville_detail
        form.metiers.data2 = self.org.metiers_detail
        # form.secteurs_activite_medias.data2 = self.org.secteurs_activite_medias_detail
        if profile_code in {
            ProfileEnum.PR_DIR_COM,
            ProfileEnum.PR_CS_COM,
        }:
            form.secteurs_activite_rp.data2 = self.org.secteurs_activite_rp_detail
        form.secteurs_activite.data2 = self.org.secteurs_activite_detail
        form.type_organisation.data2 = self.org.type_organisation_detail

        return form

    def form_transformer(self) -> FlaskForm:
        profile = self.user.profile
        profile_code = ProfileEnum[profile.profile_code]

        class BWDynForm(FlaskForm):
            pass

        BWDynForm.name = string_field(
            "name",
            description=("Nom de l’organisation"),
            mandatory=True,
            readonly=self.readonly,
        )

        if profile_code not in {
            ProfileEnum.TR_CS_ORG_IND,
            ProfileEnum.TR_DIR_SU_ORG,
            ProfileEnum.TR_DIR_POLE,
        }:
            BWDynForm.nom_groupe = string_field(
                "nom_groupe",
                "Nom du groupe, ministère, de l’administration publique ou de la fédération",
                False,
                self.readonly,
            )

        BWDynForm.siren = string_field("siren", "Numéro SIREN", True, self.readonly)
        BWDynForm.tva = string_field(
            "tva", "Numéro de TVA intracommunataire", True, self.readonly
        )
        BWDynForm.leader_name = string_field(
            "leader_name", "Nom du dirigeant", True, self.readonly
        )
        BWDynForm.leader_coords = textarea_field(
            "leader_coords", "Coordonées du dirigeant", True, self.readonly
        )
        BWDynForm.payer_name = string_field(
            "payer_name", "Nom du payeur", True, self.readonly
        )
        BWDynForm.payer_coords = textarea_field(
            "payer_coords", "Coordonées du payeur", True, self.readonly
        )
        BWDynForm.description = textarea_field(
            "description", "Description", True, self.readonly
        )
        BWDynForm.tel_standard = tel_field(
            "tel_standard", "Téléphone (standard)", True, self.readonly
        )
        BWDynForm.pays_zip_ville = country_code_field(
            "pays_zip_ville",
            "Pays;Code postal et ville",
            False,
            ontology_map="country_pays",
            readonly=self.readonly,
        )
        BWDynForm.taille_orga = list_field(
            "taille_orga",
            "Taille organisation (effectif)",
            True,
            ontology_map="list_taille_orga",
            readonly=self.readonly,
        )

        BWDynForm.type_organisation = dual_multi_field(
            "type_organisation",
            "Type d'organisation; Détail",
            True,
            "multidual_type_orga",
            self.readonly,
        )

        # BWDynForm.type_entreprise_media = multi_field(
        #     "type_entreprise_media",
        #     "Types d’entreprise de presse",
        #     True,
        #     "multi_type_entreprise_medias",
        #     readonly=self.readonly,
        # )

        # BWDynForm.type_agence_rp = multi_field(
        #     "type_agence_rp",
        #     "Type de PR agency",
        #     True,
        #     "multi_type_agences_rp",
        #     readonly=self.readonly,
        # )

        BWDynForm.transformation_majeure = dual_multi_field(
            "transformation_majeure",
            "Pour quelles transformations majeures apportez-vous votre expertise ? ; Transformations",
            True,
            "multidual_transformation_majeure",
            readonly=self.readonly,
        )

        BWDynForm.metiers_presse = multi_field(
            "metiers_presse",
            "Métiers de la presse",
            False,
            "multi_fonctions_journalisme",
            readonly=self.readonly,
        )
        BWDynForm.metiers = dual_multi_field(
            "metiers",
            "Le cas échéant, quels autres métiers exercez-vous ?; Métiers",
            False,
            "multidual_metiers",
            self.readonly,
        )
        BWDynForm.secteurs_activite = dual_multi_field(
            "secteurs_activite",
            "Secteurs d’activité dans lequel exerce votre organisation; Sous secteurs",
            True,
            "multidual_secteurs_detail",
            self.readonly,
        )

        BWDynForm.main_events = textarea_field(
            "main_events", "Principaux Events organisés", False, self.readonly
        )
        BWDynForm.main_customers = textarea_field(
            "main_customers", "Principales références clients", False, self.readonly
        )
        BWDynForm.main_prizes = textarea_field(
            "main_prizes", "Prix et autres distinctions", False, self.readonly
        )
        BWDynForm.positionnement_editorial = textarea_field(
            "positionnement_editorial", "Positionnement éditorial", False, self.readonly
        )
        BWDynForm.audience_cible = textarea_field(
            "audience_cible", "Audiences ciblées", False, self.readonly
        )
        BWDynForm.tirage = string_field("tirage", "Tirage", False, self.readonly)
        BWDynForm.frequence_publication = string_field(
            "frequence_publication", "Fréquence de publication", False, self.readonly
        )

        BWDynForm.agree_arcom = bool_field(
            "agree_arcom", "Agréé ARCOM", False, self.readonly
        )
        BWDynForm.agree_cppap = bool_field(
            "agree_cppap", "Agréé CPPAP", False, self.readonly
        )
        BWDynForm.number_cppap = string_field(
            "number_cppap", "Numéro CPPAP", False, self.readonly
        )
        BWDynForm.membre_sapi = bool_field(
            "membre_sapi", "Membre du SAPI", False, self.readonly
        )
        BWDynForm.membre_satev = bool_field(
            "membre_satev", "Membre du SATEV", False, self.readonly
        )
        BWDynForm.membre_saphir = bool_field(
            "membre_saphir", "Membre du SAPHIR", False, self.readonly
        )

        BWDynForm.domain = string_field("domain", "Domaine", False, self.readonly)
        BWDynForm.site_url = url_field(
            "site_url", "URL du site (web)", False, self.readonly
        )
        BWDynForm.jobs_url = url_field(
            "jobs_url", "URL du site (emplois)", False, self.readonly
        )
        BWDynForm.github_url = url_field(
            "github_url", "URL du site (github)", False, self.readonly
        )
        BWDynForm.linkedin_url = url_field(
            "linkedin_url", "URL du site (linkedin)", False, self.readonly
        )
        BWDynForm.logo_url = string_field(
            "logo_url", "URL du logo de l'organisation", False, self.readonly
        )
        BWDynForm.cover_image_url = url_field(
            "cover_image_url", "URL de l'image de présentation", False, self.readonly
        )

        form = BWDynForm(obj=self.org)
        form.pays_zip_ville.data2 = self.org.pays_zip_ville_detail
        form.metiers.data2 = self.org.metiers_detail
        # form.secteurs_activite_medias.data2 = self.org.secteurs_activite_medias_detail
        form.secteurs_activite.data2 = self.org.secteurs_activite_detail
        form.type_organisation.data2 = self.org.type_organisation_detail
        form.transformation_majeure.data2 = self.org.transformation_majeure_detail

        return form

    def form_academics(self) -> FlaskForm:
        profile = self.user.profile
        profile_code = ProfileEnum[profile.profile_code]

        class BWDynForm(FlaskForm):
            pass

        BWDynForm.name = string_field(
            "name",
            description=("Nom de l’organisation"),
            mandatory=True,
            readonly=self.readonly,
        )

        if profile_code not in {
            ProfileEnum.AC_DOC,
            ProfileEnum.AC_ST,
            ProfileEnum.AC_ST_ENT,
        }:
            BWDynForm.nom_groupe = string_field(
                "nom_groupe",
                "Nom du groupe, ministère, de l’administration publique ou de la fédération",
                False,
                self.readonly,
            )

        BWDynForm.siren = string_field("siren", "Numéro SIREN", True, self.readonly)
        BWDynForm.tva = string_field(
            "tva", "Numéro de TVA intracommunataire", True, self.readonly
        )
        BWDynForm.leader_name = string_field(
            "leader_name", "Nom du dirigeant", True, self.readonly
        )
        BWDynForm.leader_coords = textarea_field(
            "leader_coords", "Coordonées du dirigeant", True, self.readonly
        )
        BWDynForm.payer_name = string_field(
            "payer_name", "Nom du payeur", True, self.readonly
        )
        BWDynForm.payer_coords = textarea_field(
            "payer_coords", "Coordonées du payeur", True, self.readonly
        )
        BWDynForm.description = textarea_field(
            "description", "Description", True, self.readonly
        )
        BWDynForm.tel_standard = tel_field(
            "tel_standard", "Téléphone (standard)", True, self.readonly
        )
        BWDynForm.pays_zip_ville = country_code_field(
            "pays_zip_ville",
            "Pays;Code postal et ville",
            False,
            ontology_map="country_pays",
            readonly=self.readonly,
        )
        BWDynForm.taille_orga = list_field(
            "taille_orga",
            "Taille organisation (effectif)",
            True,
            ontology_map="list_taille_orga",
            readonly=self.readonly,
        )

        BWDynForm.type_organisation = dual_multi_field(
            "type_organisation",
            "Type d'organisation; Détail",
            True,
            "multidual_type_orga",
            self.readonly,
        )

        # BWDynForm.type_entreprise_media = multi_field(
        #     "type_entreprise_media",
        #     "Types d’entreprise de presse",
        #     True,
        #     "multi_type_entreprise_medias",
        #     readonly=self.readonly,
        # )

        # BWDynForm.type_agence_rp = multi_field(
        #     "type_agence_rp",
        #     "Type de PR agency",
        #     True,
        #     "multi_type_agences_rp",
        #     readonly=self.readonly,
        # )

        BWDynForm.metiers_presse = multi_field(
            "metiers_presse",
            "Métiers de la presse",
            False,
            "multi_fonctions_journalisme",
            readonly=self.readonly,
        )
        BWDynForm.metiers = dual_multi_field(
            "metiers",
            "Le cas échéant, quels autres métiers exercez-vous ?; Métiers",
            False,
            "multidual_metiers",
            self.readonly,
        )
        BWDynForm.secteurs_activite = dual_multi_field(
            "secteurs_activite",
            "Secteurs d’activité dans lequel exerce votre organisation; Sous secteurs",
            True,
            "multidual_secteurs_detail",
            self.readonly,
        )

        BWDynForm.main_events = textarea_field(
            "main_events", "Principaux Events organisés", False, self.readonly
        )
        BWDynForm.main_customers = textarea_field(
            "main_customers", "Principales références clients", False, self.readonly
        )
        BWDynForm.main_prizes = textarea_field(
            "main_prizes", "Prix et autres distinctions", False, self.readonly
        )
        BWDynForm.positionnement_editorial = textarea_field(
            "positionnement_editorial", "Positionnement éditorial", False, self.readonly
        )
        BWDynForm.audience_cible = textarea_field(
            "audience_cible", "Audiences ciblées", False, self.readonly
        )
        BWDynForm.tirage = string_field("tirage", "Tirage", False, self.readonly)
        BWDynForm.frequence_publication = string_field(
            "frequence_publication", "Fréquence de publication", False, self.readonly
        )

        BWDynForm.agree_arcom = bool_field(
            "agree_arcom", "Agréé ARCOM", False, self.readonly
        )
        BWDynForm.agree_cppap = bool_field(
            "agree_cppap", "Agréé CPPAP", False, self.readonly
        )
        BWDynForm.number_cppap = string_field(
            "number_cppap", "Numéro CPPAP", False, self.readonly
        )
        BWDynForm.membre_sapi = bool_field(
            "membre_sapi", "Membre du SAPI", False, self.readonly
        )
        BWDynForm.membre_satev = bool_field(
            "membre_satev", "Membre du SATEV", False, self.readonly
        )
        BWDynForm.membre_saphir = bool_field(
            "membre_saphir", "Membre du SAPHIR", False, self.readonly
        )

        BWDynForm.domain = string_field("domain", "Domaine", False, self.readonly)
        BWDynForm.site_url = url_field(
            "site_url", "URL du site (web)", False, self.readonly
        )
        BWDynForm.jobs_url = url_field(
            "jobs_url", "URL du site (emplois)", False, self.readonly
        )
        BWDynForm.github_url = url_field(
            "github_url", "URL du site (github)", False, self.readonly
        )
        BWDynForm.linkedin_url = url_field(
            "linkedin_url", "URL du site (linkedin)", False, self.readonly
        )
        BWDynForm.logo_url = string_field(
            "logo_url", "URL du logo de l'organisation", False, self.readonly
        )
        BWDynForm.cover_image_url = url_field(
            "cover_image_url", "URL de l'image de présentation", False, self.readonly
        )

        form = BWDynForm(obj=self.org)
        form.pays_zip_ville.data2 = self.org.pays_zip_ville_detail
        form.metiers.data2 = self.org.metiers_detail
        # form.secteurs_activite_medias.data2 = self.org.secteurs_activite_medias_detail
        form.secteurs_activite.data2 = self.org.secteurs_activite_detail
        form.type_organisation.data2 = self.org.type_organisation_detail

        return form

    def merge_form(self, results: dict[str, Any]) -> None:  # noqa: PLR0915
        # to adapt for the various BW types
        def _parse_bool(key: str) -> bool:
            content = results.get(key, [])
            if not content:
                return False
            return bool(content[0])

        def _parse_first(key: str) -> str:
            content = results.get(key, [])
            if not content:
                return ""
            return content[0]

        def _parse_list(key: str) -> list:
            return results.get(key, [])

        org = self.org
        org.name = _parse_first("name")
        org.nom_groupe = _parse_first("nom_groupe")
        org.siren = _parse_first("siren")
        org.tva = _parse_first("tva")
        org.leader_name = _parse_first("leader_name")  #
        org.leader_coords = _parse_first("leader_coords")  #
        org.payer_name = _parse_first("payer_name")  #
        org.payer_coords = _parse_first("payer_coords")  #
        org.description = _parse_first("description")  #
        org.tel_standard = _parse_first("tel_standard")  #
        org.pays_zip_ville = _parse_first("pays_zip_ville")
        org.pays_zip_ville_detail = _parse_first("pays_zip_ville_detail")
        org.taille_orga = _parse_first("taille_orga")  #

        org.type_organisation = _parse_list("type_organisation")
        org.type_organisation_detail = _parse_list("type_organisation_detail")
        org.type_entreprise_media = _parse_list("type_agence_rp")
        org.type_presse_et_media = _parse_list("type_presse_et_media")
        org.type_agence_rp = _parse_list("type_agence_rp")

        org.metiers_presse = _parse_list("metiers_presse")
        org.metiers = _parse_list("metiers")  #
        org.metiers_detail = _parse_list("metiers_detail")  #
        org.secteurs_activite_medias = _parse_list("secteurs_activite_medias")
        org.secteurs_activite_medias_detail = _parse_list(
            "secteurs_activite_medias_detail"
        )
        org.secteurs_activite_rp = _parse_list("secteurs_activite_rp")
        org.secteurs_activite_rp_detail = _parse_list("secteurs_activite_rp_detail")
        org.secteurs_activite = _parse_list("secteurs_activite")
        org.secteurs_activite_detail = _parse_list("secteurs_activite_detail")

        org.transformation_majeure = _parse_list("transformation_majeure")
        org.transformation_majeure_detail = _parse_list("transformation_majeure_detail")

        org.main_events = _parse_first("main_events")
        org.main_customers = _parse_first("main_customers")
        org.main_prizes = _parse_first("main_prizes")
        org.positionnement_editorial = _parse_first("positionnement_editorial")
        org.audience_cible = _parse_first("audience_cible")
        org.tirage = _parse_first("tirage")
        org.frequence_publication = _parse_first("frequence_publication")

        org.agree_arcom = _parse_bool("agree_arcom")  #
        org.agree_cppap = _parse_bool("agree_cppap")  #
        org.number_cppap = _parse_first("number_cppap")  #
        org.membre_satev = _parse_bool("membre_satev")  #
        org.membre_sapi = _parse_bool("membre_sapi")  #
        org.membre_saphir = _parse_bool("membre_saphir")  #
        org.domain = _parse_first("domain")
        org.site_url = _parse_first("site_url")
        org.jobs_url = _parse_first("jobs_url")
        org.github_url = _parse_first("github_url")
        org.linkedin_url = _parse_first("linkedin_url")
        org.logo_url = _parse_first("logo_url")
        org.cover_image_url = _parse_first("cover_image_url")

        db_session = db.session
        db_session.merge(self.org)
        db_session.commit()


def string_field(
    name="", description="", mandatory: bool = False, readonly: bool = False
) -> Field:
    survey_field = SurveyField(
        id=name, name=name, type="string", description=description
    )
    mandatory_code = "M" if mandatory else ""
    return custom_string_field(
        survey_field, mandatory_code=mandatory_code, readonly=readonly
    )


def bool_field(
    name="", description="", mandatory: bool = False, readonly: bool = False
) -> Field:
    survey_field = SurveyField(
        id=name, name=name, type="boolean", description=description
    )
    mandatory_code = "M" if mandatory else ""
    return custom_bool_field(
        survey_field, mandatory_code=mandatory_code, readonly=readonly
    )


def textarea_field(
    name="", description="", mandatory: bool = False, readonly: bool = False
) -> Field:
    survey_field = SurveyField(
        id=name, name=name, type="textarea", description=description
    )
    mandatory_code = "M" if mandatory else ""
    return custom_textarea_field(
        survey_field, mandatory_code=mandatory_code, readonly=readonly
    )


def tel_field(
    name="", description="", mandatory: bool = False, readonly: bool = False
) -> Field:
    survey_field = SurveyField(id=name, name=name, type="tel", description=description)
    mandatory_code = "M" if mandatory else ""
    return custom_tel_field(
        survey_field, mandatory_code=mandatory_code, readonly=readonly
    )


def url_field(
    name="", description="", mandatory: bool = False, readonly: bool = False
) -> Field:
    survey_field = SurveyField(id=name, name=name, type="url", description=description)
    mandatory_code = "M" if mandatory else ""
    return custom_url_field(
        survey_field, mandatory_code=mandatory_code, readonly=readonly
    )


def list_field(
    name="",
    description="",
    mandatory: bool = False,
    ontology_map: str = "",
    readonly: bool = False,
) -> Field:
    survey_field = SurveyField(id=name, name=name, type="list", description=description)
    mandatory_code = "M" if mandatory else ""
    return custom_list_field(
        survey_field,
        mandatory_code=mandatory_code,
        param=ontology_map,
        readonly=readonly,
    )


def dual_multi_field(
    name="",
    description="",
    mandatory: bool = False,
    ontology_map: str = "",
    readonly: bool = False,
) -> Field:
    survey_field = SurveyField(
        id=name, name=name, type="multidual", description=description
    )
    mandatory_code = "M" if mandatory else ""
    return custom_dual_multi_field(
        survey_field,
        mandatory_code=mandatory_code,
        param=ontology_map,
        readonly=readonly,
    )


def multi_field(
    name="",
    description="",
    mandatory: bool = False,
    ontology_map: str = "",
    readonly: bool = False,
) -> Field:
    survey_field = SurveyField(
        id=name, name=name, type="multi", description=description
    )
    mandatory_code = "M" if mandatory else ""
    return custom_multi_field(
        survey_field,
        mandatory_code=mandatory_code,
        param=ontology_map,
        readonly=readonly,
    )


def country_code_field(
    name="",
    description="",
    mandatory: bool = False,
    ontology_map: str = "",
    readonly: bool = False,
) -> Field:
    survey_field = SurveyField(
        id=name, name=name, type="country", description=description
    )
    mandatory_code = "M" if mandatory else ""
    return custom_country_field(
        survey_field,
        mandatory_code=mandatory_code,
        param=ontology_map,
        readonly=readonly,
    )
