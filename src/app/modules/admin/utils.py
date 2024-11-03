# Copyright (c) 2021-2024 - Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from arrow import now
from flask_sqlalchemy.session import Session
from sqlalchemy import false, func, select, true
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import scoped_session

from app.constants import LABEL_MODIFICATION_ORGANISATION, LOCAL_TZ
from app.enums import OrganisationTypeEnum
from app.flask.extensions import db
from app.flask.sqla import get_obj
from app.models.auth import User, clone_kycprofile
from app.models.organisation import Organisation


def get_user_per_email(email: str) -> User | None:
    """Return the User with provided email, or None."""
    email = email.strip().lower()
    if not email:
        return None
    if "@" not in email:
        return None
    stmt = select(User).where(
        User.active == true(),
        User.is_clone == false(),
        User.deleted_at.is_(None),
        func.lower(User.email) == email,
    )
    return db.session.scalar(stmt)


def _remove_organisational_roles(user: User) -> None:
    for role in ("LEADER", "MANAGER"):
        # Question: shall we remove all this:
        # for role in ("LEADER" , "MANAGER", "PRESS_MEDIA", "PRESS_RELATIONS",  "EXPERT", "ACADEMIC", "TRANSFORMER" ):
        user.remove_role(role)


def _remove_user_organisation(user: User) -> None:
    previous_organisation = user.organisation
    if previous_organisation:
        _remove_organisational_roles(user)
        user.organisation_id = None


def _remove_user_profile_organisation(user: User) -> None:
    new_profile = clone_kycprofile(user.profile)
    new_profile.info_professionnelle["nom_adm"] = ""
    new_profile.info_professionnelle["nom_agence_rp"] = ""
    new_profile.info_professionnelle["nom_group_com"] = ""
    new_profile.info_professionnelle["nom_groupe_presse"] = ""
    new_profile.info_professionnelle["nom_media_instit"] = ""
    new_profile.info_professionnelle["nom_orga"] = ""
    new_profile.info_professionnelle["nom_media"] = []
    user.profile = new_profile


def _set_user_organisation_id(user: User, org_id: int) -> None:
    user.organisation_id = org_id


def _set_user_profile_organisation(user: User, organisation: Organisation) -> None:
    new_profile = clone_kycprofile(user.profile)
    name = organisation.name
    match organisation.type:
        case OrganisationTypeEnum.MEDIA:
            new_profile.info_professionnelle["nom_media"] = [name]
        case OrganisationTypeEnum.AGENCY:
            new_profile.info_professionnelle["nom_media"] = [name]
        case OrganisationTypeEnum.COM:
            new_profile.info_professionnelle["nom_agence_rp"] = name
        case OrganisationTypeEnum.OTHER:
            new_profile.info_professionnelle["nom_orga"] = name
        case OrganisationTypeEnum.AUTO:
            new_profile.info_professionnelle["nom_orga"] = name
    # new_profile.info_professionnelle["nom_adm"] = ""
    # new_profile.info_professionnelle["nom_media_instit"] = ""
    user.profile = new_profile


def commit_session(db_session: scoped_session[Session]) -> str:
    error = ""
    try:
        db_session.commit()
    except IntegrityError as e:
        db_session.rollback()
        error = str(e)
    return error


def set_user_organisation(user: User, organisation: Organisation) -> str:
    """Change the user's Organisation with the provided one, adapting
    (some) KYC fields.
    """
    db_session = db.session
    _remove_user_organisation(user)
    _remove_user_profile_organisation(user)
    _set_user_organisation_id(user, organisation.id)
    _set_user_profile_organisation(user, organisation)
    dt_now = now(LOCAL_TZ)
    user.modified_at = dt_now
    user.validated_at = dt_now
    user.validation_status = LABEL_MODIFICATION_ORGANISATION

    db_session.merge(user)
    db_session.merge(organisation)
    return commit_session(db_session)


def gc_organisation(organisation: Organisation | None) -> bool:
    """If the provided Organisation is of type AUTO and has no member: delete it.

    Return True is deletion occured.
    """
    if not organisation or not organisation.is_auto or len(organisation.members) > 0:
        return False
    # AUTO organisation with zero member: felete it
    db_session = db.session
    db_session.delete(organisation)
    db_session.commit()
    return True


def gc_all_auto_organisations() -> int:
    """Garbage collect all Organisation of type AUTO with no member.

    Return True is deletion occured.
    """
    db_session = db.session
    stmt = select(Organisation).where(
        Organisation.deleted_at.is_(None),
        Organisation.type == OrganisationTypeEnum.AUTO,
        ~Organisation.members.any(),
    )
    empty_orgs = db_session.scalars(stmt)
    counter = 0
    for organisation in empty_orgs:
        db_session.delete(organisation)
        counter += 1
    db_session.commit()
    return counter


def remove_user_organisation(user: User) -> str:
    db_session = db.session
    _remove_user_organisation(user)
    _remove_user_profile_organisation(user)
    dt_now = now(LOCAL_TZ)
    user.modified_at = dt_now
    user.validated_at = dt_now
    user.validation_status = LABEL_MODIFICATION_ORGANISATION
    db_session.merge(user)
    db_session.flush()
    db_session.commit()
    return commit_session(db_session)


def set_user_organisation_from_ids(user_id: int, org_id: int) -> str:
    """Change the user's Organisation with the provided one, adapting
    (some) KYC fields. Inputes are IDs.
    """
    user = get_obj(user_id, User)
    organisation = get_obj(user_id, Organisation)
    db_session = db.session
    _remove_user_organisation(user)
    _remove_user_profile_organisation(user)
    _set_user_organisation_id(user, organisation.id)
    _set_user_profile_organisation(user, organisation)
    dt_now = now(LOCAL_TZ)
    user.modified_at = dt_now
    user.validated_at = dt_now
    user.validation_status = LABEL_MODIFICATION_ORGANISATION

    db_session.merge(user)
    db_session.merge(organisation)
    return commit_session(db_session)
