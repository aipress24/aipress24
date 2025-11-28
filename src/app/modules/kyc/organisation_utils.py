# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from typing import Any

from sqlalchemy import func, select

from app.constants import PROFILE_CODE_TO_BW_TYPE
from app.enums import BWTypeEnum, OrganisationTypeEnum, ProfileEnum
from app.flask.extensions import db
from app.flask.sqla import get_obj
from app.models.auth import User
from app.models.invitation import Invitation
from app.models.organisation import Organisation


def get_organisation_family(
    family: OrganisationTypeEnum = OrganisationTypeEnum.AUTO,  # type: ignore
) -> list[str]:
    """Get list of Organisation of specified family."""
    query = (
        select(Organisation)
        .where(Organisation.type == family)
        .order_by(Organisation.name)
    )
    result = db.session.execute(query).scalars()
    return [org.name for org in result]


def get_organisation_for_noms_medias() -> list[str]:
    """Get list of Organisation of MEDIA AGENCY and AUTO families.

    List not filtered for duplicates.
    (Then will add the required ontologie if needed, there or in a later stage)
    """
    query = select(Organisation).where(
        Organisation.type.in_(
            [
                OrganisationTypeEnum.MEDIA,
                OrganisationTypeEnum.AGENCY,
                OrganisationTypeEnum.AUTO,
            ]
        )
    )
    result = db.session.execute(query).scalars()
    return [org.name for org in result]


def get_organisation_for_noms_orgas() -> list[str]:
    """Get list of Organisation of OTHER and AUTO families.

    List not filtered for duplicates.
    (Then will add the required ontologie if needed, there or in a later stage)
    """
    query = select(Organisation).where(
        Organisation.type.in_(
            [
                OrganisationTypeEnum.OTHER,
                OrganisationTypeEnum.AUTO,
            ]
        )
    )
    result = db.session.execute(query).scalars()
    return [org.name for org in result]


def get_organisation_for_noms_com() -> list[str]:
    """Get list of Organisation of COM and AUTO families.

    List not filtered for duplicates.
    (Then will add the required ontologie if needed, there or in a later stage)
    """
    query = select(Organisation).where(
        Organisation.type.in_(
            [
                OrganisationTypeEnum.COM,
                OrganisationTypeEnum.AUTO,
            ]
        )
    )
    result = db.session.execute(query).scalars()
    return [org.name for org in result]


def get_organisation_choices_family(
    family: OrganisationTypeEnum = OrganisationTypeEnum.AUTO,  # type: ignore
) -> list[tuple[str, str]]:
    """Get list of light organisations of specified famille in HTML select format"""
    return [(name, name) for name in get_organisation_family(family)]


def _find_kyc_organisation_name(user: User) -> str:
    profile = user.profile
    orga_field_name = profile.organisation_field_name_origin
    current_value = profile.get_value(orga_field_name)
    if isinstance(current_value, list):  # newsrooms is a list
        if current_value:
            name = current_value[0]
        else:
            name = ""
    else:
        name = current_value
    return name.strip()


def retrieve_user_organisation(user: User) -> Organisation | None:
    """Return the User's organisation, either official if invited, or auto or
    create a new User AUTO organisation if the organisation does not exists.
    """

    org_name = _find_kyc_organisation_name(user)
    if not org_name:
        return None
    # family = profile.organisation_family  # select the target family
    inviting_orgs = find_inviting_organisations(user.email)
    for org in inviting_orgs:
        if org.name.lower() == org_name.lower():
            # We found an official BW organisation inviting this user:
            return org
    # store a new AUTO organisation
    return store_auto_organisation(user, org_name=org_name)


def find_inviting_organisations(mail: str) -> list[Organisation]:
    """Return the list of all Oganisation with an invitation for provided email."""
    if not mail or "@" not in mail:
        return []
    stmt = select(Invitation).where(func.lower(Invitation.email) == mail.lower())
    invitations = db.session.scalars(stmt)
    if not invitations:
        return []
    return [get_obj(i.organisation_id, Organisation) for i in invitations]


def specialize_organization_type(
    org: Organisation,
    profile_code_str: str,
    info_pro: dict[str, Any],
    info_mm: dict[str, Any],
) -> None:
    profile_code = ProfileEnum[profile_code_str]
    allowed_bw_types = set(PROFILE_CODE_TO_BW_TYPE.get(profile_code, []))

    _set_nom_groupe(org, profile_code, info_pro)
    _set_media_types(org, allowed_bw_types, info_pro)
    _set_organization_types(org, profile_code, allowed_bw_types, info_pro)
    _set_activity_sectors(org, profile_code, allowed_bw_types, info_mm)


def _set_nom_groupe(
    org: Organisation, profile_code: ProfileEnum, info_pro: dict[str, Any]
) -> None:
    """Set nom_groupe based on profile code."""
    nom_groupe = ""
    if profile_code in {
        ProfileEnum.PM_DIR,
        ProfileEnum.PM_JR_CP_SAL,
        ProfileEnum.PM_JR_PIG,
    }:
        nom_groupe = info_pro["nom_groupe_presse"]
    elif profile_code in {ProfileEnum.PR_DIR, ProfileEnum.PR_CS}:
        nom_groupe = info_pro["nom_group_com"]
    elif profile_code in {
        ProfileEnum.PR_DIR_COM,
        ProfileEnum.PR_CS_COM,
        ProfileEnum.XP_DIR_ANY,
        ProfileEnum.XP_ANY,
        ProfileEnum.XP_PR,
        ProfileEnum.XP_INV_PUB,
        ProfileEnum.XP_DIR_EVT,
        ProfileEnum.TP_DIR_ORG,
        ProfileEnum.TR_CS_ORG,
        ProfileEnum.TR_CS_ORG_PR,
        ProfileEnum.TR_INV_ORG,
        ProfileEnum.AC_DIR,
        ProfileEnum.AC_DIR_JR,
        ProfileEnum.AC_ENS,
    }:
        nom_groupe = info_pro["nom_adm"]
    org.nom_groupe = nom_groupe


def _set_media_types(
    org: Organisation, allowed_bw_types: set, info_pro: dict[str, Any]
) -> None:
    """Set media and agency type attributes."""
    # type_entreprise_media
    type_entreprise_media = []
    if {BWTypeEnum.MEDIA, BWTypeEnum.AGENCY, BWTypeEnum.MICRO} & allowed_bw_types:
        type_entreprise_media = info_pro["type_entreprise_media"]
    org.type_entreprise_media = type_entreprise_media

    # type_presse_et_media
    type_presse_et_media = []
    if {
        BWTypeEnum.MEDIA,
        BWTypeEnum.AGENCY,
        BWTypeEnum.CORPORATE,
        BWTypeEnum.MICRO,
    } & allowed_bw_types:
        type_presse_et_media = info_pro["type_presse_et_media"]
    org.type_presse_et_media = type_presse_et_media


def _set_organization_types(
    org: Organisation,
    profile_code: ProfileEnum,
    allowed_bw_types: set,
    info_pro: dict[str, Any],
) -> None:
    """Set organization type attributes."""
    # type_agence_rp
    type_agence_rp = []
    if profile_code in {
        ProfileEnum.PR_DIR,
        ProfileEnum.PR_CS,
        ProfileEnum.PR_CS_IND,
    }:
        type_agence_rp = info_pro["type_agence_rp"]
    org.type_agence_rp = type_agence_rp

    # type_orga
    type_organisation = []
    type_organisation_detail = []
    if {
        BWTypeEnum.ORGANISATION,
        BWTypeEnum.TRANSFORMER,
        BWTypeEnum.ACADEMICS,
    } & allowed_bw_types:
        type_organisation = info_pro["type_orga"]
        type_organisation_detail = info_pro["type_orga_detail"]
    org.type_organisation = type_organisation
    org.type_organisation_detail = type_organisation_detail


def _set_activity_sectors(
    org: Organisation,
    profile_code: ProfileEnum,
    allowed_bw_types: set,
    info_mm: dict[str, Any],
) -> None:
    """Set activity sector attributes."""
    # Media sectors
    secteurs_activite_medias = []
    secteurs_activite_medias_detail = []
    if {BWTypeEnum.MEDIA, BWTypeEnum.AGENCY} & allowed_bw_types:
        secteurs_activite_medias = info_mm["secteurs_activite_medias"]
        secteurs_activite_medias_detail = info_mm["secteurs_activite_medias_detail"]
    org.secteurs_activite_medias = secteurs_activite_medias
    org.secteurs_activite_medias_detail = secteurs_activite_medias_detail

    # RP sectors
    secteurs_activite_rp = []
    secteurs_activite_rp_detail = []
    if profile_code in {
        ProfileEnum.PR_DIR,
        ProfileEnum.PR_CS,
        ProfileEnum.PR_CS_IND,
        ProfileEnum.PR_DIR_COM,
        ProfileEnum.PR_CS_COM,
    }:
        secteurs_activite_rp = info_mm["secteurs_activite_rp"]
        secteurs_activite_rp_detail = info_mm["secteurs_activite_rp_detail"]
    org.secteurs_activite_rp = secteurs_activite_rp
    org.secteurs_activite_rp_detail = secteurs_activite_rp_detail

    # General sectors
    secteurs_activite = []
    secteurs_activite_detail = []
    if {
        BWTypeEnum.COM,
        BWTypeEnum.ORGANISATION,
        BWTypeEnum.TRANSFORMER,
        BWTypeEnum.ACADEMICS,
    } & allowed_bw_types:
        secteurs_activite = info_mm["secteurs_activite_detailles"]
        secteurs_activite_detail = info_mm["secteurs_activite_detailles_detail"]
    org.secteurs_activite = secteurs_activite
    org.secteurs_activite_detail = secteurs_activite_detail

    # Transformation sectors
    transformation_majeure = []
    transformation_majeure_detail = []
    if {BWTypeEnum.TRANSFORMER} & allowed_bw_types:
        transformation_majeure = info_mm["transformation_majeure"]
        transformation_majeure_detail = info_mm["transformation_majeure_detail"]
    org.transformation_majeure = transformation_majeure
    org.transformation_majeure_detail = transformation_majeure_detail


def store_auto_organisation(
    user: User,
    org_name: str | None = None,
    db_session: object | None = None,
) -> Organisation | None:
    """Store a new AUTO organisation if the organisation does not exists.

    Return: created or existent Auto Organisation, or None if fail to create (empty name)

    2 possible situations:
        - the organisation already exists, either as a registered (MEDIA? COM...) or AUTO
            -> if of type AUTO, return the existent Organisation
            -> if of any other type, create a AUTO organisation (of same name)
        - the organisation does not exists
            -> create a new one with type "AUTO"
    """
    if org_name is None:
        # store_auto_organisation() can be called without providing the organisation na
        org_name = _find_kyc_organisation_name(user)
    org_name = str(org_name).strip()
    if not org_name:
        return None
    # identification of AUTO organisation is only the organisation name
    if db_session is None:
        db_session = db.session
    query = select(Organisation).where(
        Organisation.name == org_name, Organisation.type == OrganisationTypeEnum.AUTO
    )
    found_organisation = db.session.execute(query).scalars().first()
    if found_organisation:
        return found_organisation
    # No Organisatin with both same type and other params found:
    created_organisation = Organisation(name=org_name, type=OrganisationTypeEnum.AUTO)
    db_session.add(created_organisation)
    db_session.flush()
    return created_organisation


# def store_auto_organisation(
# Too complex: prefer a minimalistic approach for AUTO organizations : only name
# ##############################################################################
#     user: User,
#     org_name: str | None = None,
#     # family: OrganisationTypeEnum = OrganisationTypeEnum.AUTO,  # type: ignore
#     db_session: object | None = None,
# ) -> Organisation | None:
#     """Store a new AUTO organisation if the organisation does not exists.

#     Return: created or existent Auto Organisation, or None if fail to create (empty name)

#     2 possible situations:
#         - the organisation already exists, either as a registered (MEDIA? COM...) or AUTO
#             -> if of type AUTO, return the existent Organisation
#             -> if of any other type, create a AUTO organisation (of same name)
#         - the organisation does not exists
#             -> create a new one with type "AUTO"
#     """

#     def _secteur_activite(info: dict[str, Any]) -> list[str]:
#         return (
#             info["secteurs_activite_detailles"]
#             or info["secteurs_activite_medias"]
#             or info["secteurs_activite_rp"]
#         )

#     def _secteur_activite_detail(info: dict[str, Any]) -> list[str]:
#         return (
#             info["secteurs_activite_detailles_detail"]
#             or info["secteurs_activite_medias_detail"]
#             or info["secteurs_activite_rp_detail"]
#         )

#     if org_name is None:
#         # store_auto_organisation() can be called without providing the organisation na
#         org_name = _find_kyc_organisation_name(user)
#     org_name = str(org_name).strip()
#     if not org_name:
#         return None
#     # identificatin of AUTO organisation is:
#     # - organisation name
#     # - le secteur d’activité (cf ONTOLOGIES/Secteurs détaillés) ;
#     # -> org.secteurs_activite, secteurs_activite_detail
#     # - le type d'organisation (cf ONTOLOGIES/Types d'organisation) ;
#     # -> type_organisation, type_organisation_detail
#     # - la taille de l’organisation (cf ONTOLOGIES / Taille des organisations) ;
#     # -> taille_orga
#     # - la géolocalisation (code postal, commune) du siège social ;
#     # -> pays_zip_ville, pays_zip_ville_detail
#     # - et type == AUTO
#     profile = user.profile
#     info_pro: dict[str, Any] = profile.info_professionnelle
#     info_mm: dict[str, Any] = profile.match_making
#     secteurs_activite = _secteur_activite(info_mm)
#     secteurs_activite_detail = _secteur_activite_detail(info_mm)

#     if db_session is None:
#         db_session = db.session
#     query = select(Organisation).where(
#         Organisation.name == org_name, Organisation.type == OrganisationTypeEnum.AUTO
#     )
#     found_organisations = db.session.execute(query).scalars()

#     matching_org = None
#     for org in found_organisations:
#         if (
#             org.secteurs_activite == secteurs_activite
#             and org.secteurs_activite_detail == secteurs_activite_detail
#             and org.type_organisation == info_pro["type_orga"]
#             and org.type_organisation_detail == info_pro["type_orga_detail"]
#             and org.taille_orga == info_pro["taille_orga"]
#             and org.pays_zip_ville == info_pro["pays_zip_ville"]
#             and org.pays_zip_ville_detail == info_pro["pays_zip_ville_detail"]
#         ):
#             matching_org = org
#             break

#     if matching_org:
#         return matching_org
#     # No Organisatin with both same type and other params found:
#     created_organisation = Organisation(
#         name=org_name,
#         type=OrganisationTypeEnum.AUTO,
#         taille_orga=info_pro["taille_orga"],
#         pays_zip_ville=info_pro["pays_zip_ville"],
#         pays_zip_ville_detail=info_pro["pays_zip_ville_detail"],
#         tel_standard=info_pro["tel_standard"],
#     )

#     specialize_organization_type(
#         created_organisation, profile.profile_code, info_pro, info_mm
#     )

#     db_session.add(created_organisation)
#     db_session.commit()
#     return created_organisation
