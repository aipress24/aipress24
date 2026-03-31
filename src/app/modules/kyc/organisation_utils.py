# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from sqlalchemy import func, select, true

from app.flask.extensions import db
from app.flask.sqla import get_obj
from app.models.auth import User
from app.models.invitation import Invitation
from app.models.organisation import Organisation


def get_organisation_family() -> list[str]:
    """FIXME: there is no organisation type

    Get list of Organisation of ANY family."""
    query = (
        select(Organisation)
        .where(Organisation.active == true())
        .order_by(Organisation.name)
    )
    result = db.session.execute(query).scalars()
    return [org.name for org in result]


def get_organisation_for_noms_medias() -> list[str]:
    """FIXME: there is no organisation type

    Get list of Organisation of MEDIA AGENCY and AUTO families.

    List not filtered for duplicates.
    (Then will add the required ontologie if needed, there or in a later stage)
    """
    # query = select(Organisation).where(
    #     Organisation.type.in_(
    #         [
    #             OrganisationTypeEnum.MEDIA,
    #             OrganisationTypeEnum.AGENCY,
    #             OrganisationTypeEnum.AUTO,
    #         ]
    #     )
    # )
    query = (
        select(Organisation)
        .where(Organisation.active == true())
        .order_by(Organisation.name)
    )
    result = db.session.execute(query).scalars()
    return [org.name for org in result]


def get_organisation_for_noms_orgas() -> list[str]:
    """FIXME: there is no organisation type

    Get list of Organisation of OTHER and AUTO families.

    List not filtered for duplicates.
    (Then will add the required ontologie if needed, there or in a later stage)
    """
    # query = select(Organisation).where(
    #     Organisation.type.in_(
    #         [
    #             OrganisationTypeEnum.OTHER,
    #             OrganisationTypeEnum.AUTO,
    #         ]
    #     )
    # )
    query = (
        select(Organisation)
        .where(Organisation.active == true())
        .order_by(Organisation.name)
    )
    result = db.session.execute(query).scalars()
    return [org.name for org in result]


def get_organisation_for_noms_com() -> list[str]:
    """FIXME: there is no organisation type

    Get list of Organisation of COM and AUTO families.

    List not filtered for duplicates.
    (Then will add the required ontologie if needed, there or in a later stage)
    """
    # query = select(Organisation).where(
    #     Organisation.type.in_(
    #         [
    #             OrganisationTypeEnum.COM,
    #             OrganisationTypeEnum.AUTO,
    #         ]
    #     )
    # )
    query = (
        select(Organisation)
        .where(Organisation.active == true())
        .order_by(Organisation.name)
    )
    result = db.session.execute(query).scalars()
    return [org.name for org in result]


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
        name = current_value or ""
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


def store_auto_organisation(
    user: User,
    org_name: str | None = None,
    db_session: object | None = None,
) -> Organisation | None:
    """Store a new AUTO organisation if the organisation does not exists.

    FIXME: Organisation have no type

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
    query = select(Organisation).where(Organisation.name == org_name)
    found_organisation = db.session.execute(query).scalars().first()
    if found_organisation:
        return found_organisation
    # No Organisatin with both same type and other params found:
    created_organisation = Organisation(name=org_name, active=True)
    db_session.add(created_organisation)
    db_session.flush()
    return created_organisation
