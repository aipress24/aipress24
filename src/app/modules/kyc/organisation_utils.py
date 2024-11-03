# Copyright (c) 2021-2024 - Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from sqlalchemy import func, select

from app.enums import OrganisationTypeEnum
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
        Organisation.type.in_([
            OrganisationTypeEnum.MEDIA,
            OrganisationTypeEnum.AGENCY,
            OrganisationTypeEnum.AUTO,
        ])
    )
    result = db.session.execute(query).scalars()
    return [org.name for org in result]


def get_organisation_for_noms_orgas() -> list[str]:
    """Get list of Organisation of OTHER and AUTO families.

    List not filtered for duplicates.
    (Then will add the required ontologie if needed, there or in a later stage)
    """
    query = select(Organisation).where(
        Organisation.type.in_([
            OrganisationTypeEnum.OTHER,
            OrganisationTypeEnum.AUTO,
        ])
    )
    result = db.session.execute(query).scalars()
    return [org.name for org in result]


def get_organisation_for_noms_com() -> list[str]:
    """Get list of Organisation of COM and AUTO families.

    List not filtered for duplicates.
    (Then will add the required ontologie if needed, there or in a later stage)
    """
    query = select(Organisation).where(
        Organisation.type.in_([
            OrganisationTypeEnum.COM,
            OrganisationTypeEnum.AUTO,
        ])
    )
    result = db.session.execute(query).scalars()
    return [org.name for org in result]


def get_organisation_choices_family(
    family: OrganisationTypeEnum = OrganisationTypeEnum.AUTO,  # type: ignore
) -> list[tuple[str, str]]:
    """Get list of light organisations of specified famille in HTML select format"""
    return [(name, name) for name in get_organisation_family(family)]


def retrieve_user_organisation(user: User) -> Organisation | None:
    """Return the User's organisation, either official if invited, or auto or
    create a new User AUTO organisation if the organisation does not exists.
    """
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
    name = name.strip()
    if not name:
        return None
    # family = profile.organisation_family  # select the target family
    inviting_orgs = find_inviting_organisations(user.email)
    for org in inviting_orgs:
        if org.name.lower() == name.lower():
            return org
    return store_auto_organisation(name)


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
    name: str = "",
    # family: OrganisationTypeEnum = OrganisationTypeEnum.AUTO,  # type: ignore
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
    name = str(name).strip()
    if not name:
        return None
    if db_session is None:
        db_session = db.session
    query = (
        select(Organisation).where(
            Organisation.name == name, Organisation.type == OrganisationTypeEnum.AUTO
        )
        # .where(Organisation.type.in_([family, OrganisationTypeEnum.AUTO]))
    )
    found_organisation = db.session.execute(query).scalar()
    if found_organisation:
        return found_organisation
    # No Organisatin with both same type and name exists: save
    created_organisation = Organisation(name=name, type=OrganisationTypeEnum.AUTO)
    db_session.add(created_organisation)
    db_session.commit()
    return created_organisation
