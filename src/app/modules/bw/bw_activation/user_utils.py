# Copyright (c) 2025, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Utility functions for Business Wall activation workflow."""

from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING, cast
from uuid import UUID

from flask import g, session
from sqlalchemy import inspect, select
from sqlalchemy.exc import NoInspectionAvailable

from app.enums import ProfileEnum
from app.flask.extensions import db
from app.logging import warn
from app.modules.admin.utils import Organisation
from app.modules.bw.bw_activation.models import (
    BusinessWall,
    BWRoleType,
    InvitationStatus,
    RoleAssignment,
)
from app.modules.bw.bw_activation.models.business_wall import BWStatus, BWType

StdDict = dict[str, str | int | float | bool | None]

if TYPE_CHECKING:
    from app.models.auth import User

PROFILE_CODE_TO_BW2_TYPE: dict[ProfileEnum, BWType | str] = {
    ProfileEnum.PM_DIR: BWType.MEDIA,
    ProfileEnum.PM_JR_CP_SAL: BWType.MEDIA,  # open to all employees
    ProfileEnum.PM_JR_PIG: BWType.MEDIA,  # open to all employees
    ProfileEnum.PM_JR_CP_ME: BWType.MICRO,
    ProfileEnum.PM_JR_ME: BWType.MICRO,
    ProfileEnum.PM_DIR_INST: BWType.CORPORATE_MEDIA,
    ProfileEnum.PM_JR_INST: BWType.CORPORATE_MEDIA,  # open to all employees
    ProfileEnum.PM_DIR_SYND: BWType.UNION,
    ProfileEnum.PR_DIR: BWType.PR,
    ProfileEnum.PR_CS: BWType.PR,  # open to all employees
    ProfileEnum.PR_CS_IND: BWType.PR,
    ProfileEnum.PR_DIR_COM: BWType.PR,
    ProfileEnum.PR_CS_COM: BWType.PR,  # open to all employees
    ProfileEnum.XP_DIR_ANY: BWType.LEADERS_EXPERTS,
    ProfileEnum.XP_ANY: BWType.LEADERS_EXPERTS,  # open to all employees
    ProfileEnum.XP_PR: BWType.LEADERS_EXPERTS,  # open to all employees
    ProfileEnum.XP_IND: BWType.LEADERS_EXPERTS,
    ProfileEnum.XP_DIR_SU: BWType.LEADERS_EXPERTS,
    ProfileEnum.XP_INV_PUB: BWType.LEADERS_EXPERTS,
    ProfileEnum.XP_DIR_EVT: BWType.LEADERS_EXPERTS,
    ProfileEnum.TP_DIR_ORG: BWType.TRANSFORMERS,
    ProfileEnum.TR_CS_ORG: BWType.TRANSFORMERS,  # open to all employees
    ProfileEnum.TR_CS_ORG_PR: BWType.TRANSFORMERS,  # open to all employees
    ProfileEnum.TR_CS_ORG_IND: BWType.TRANSFORMERS,
    ProfileEnum.TR_DIR_SU_ORG: BWType.TRANSFORMERS,
    ProfileEnum.TR_INV_ORG: BWType.TRANSFORMERS,
    ProfileEnum.TR_DIR_POLE: BWType.TRANSFORMERS,
    ProfileEnum.AC_DIR: BWType.ACADEMICS,
    ProfileEnum.AC_DIR_JR: BWType.ACADEMICS,
    ProfileEnum.AC_ENS: BWType.ACADEMICS,  # open to all employees
    ProfileEnum.AC_DOC: BWType.ACADEMICS,  # open to all employees
    ProfileEnum.AC_ST: BWType.MICRO,  # open to all employees except students
    ProfileEnum.AC_ST_ENT: BWType.ACADEMICS,
}


def get_current_user_data() -> StdDict:
    data: StdDict = {}
    user = cast("User", g.user)
    org = user.organisation

    # Pick the "fonction" contextualised to the BW type being activated,
    # otherwise `metier_fonction` would often return a misleading value
    # (bug #0107). Falls back to `metier_fonction` when bw_type unknown.
    bw_type = session.get("bw_type")
    data.update(
        {
            "first_name": user.first_name,
            "last_name": user.last_name,
            "phone": user.tel_mobile,
            "email": user.email,
            "fonction": user.metier_fonction_for_bw(bw_type),
            "allow_activation": (org and org.is_auto_or_inactive),
        }
    )
    return data


def guess_best_bw_type(user: User) -> BWType:
    profile = user.profile
    try:
        profile_code = ProfileEnum[profile.profile_code]
    except KeyError:
        return BWType.MEDIA  # type: ignore[invalid-return-type]  # ty:ignore[invalid-return-type]
    return PROFILE_CODE_TO_BW2_TYPE.get(profile_code, BWType.MEDIA)  # type: ignore[invalid-return-type]  # ty:ignore[invalid-return-type]


def get_any_business_wall_for_organisation(org: Organisation) -> BusinessWall | None:
    """Returns the a BusinessWall of any type associated with this organisation."""
    session = inspect(org).session
    if session is None:
        return None
    stmt = (
        select(BusinessWall)
        .where(BusinessWall.organisation_id == org.id)
        .order_by(BusinessWall.created_at.desc())
    )
    return session.execute(stmt).scalars().first()


def get_active_business_wall_for_organisation(org: Organisation) -> BusinessWall | None:
    """Returns the active BusinessWall associated with this organisation."""
    session = inspect(org).session
    if session is None:
        return None
    if org.bw_id is None:
        return None
    stmt = (
        select(BusinessWall)
        .where(BusinessWall.id == org.bw_id)
        .where(BusinessWall.status == BWStatus.ACTIVE.value)
    )
    return session.execute(stmt).scalars().one_or_none()


def is_organisation_an_agency(org: Organisation) -> bool:
    result: bool = False
    if org.bw_active == "media":
        bw = get_active_business_wall_for_organisation(org)
        if bw and "Agence de presse" in bw.type_entreprise_media:
            result = True
    warn(f"BW {bw.name} is agency: {result}")
    return result

    # Deprecated implementation
    # stmt = (
    #     select(BusinessWall)
    #     .where(BusinessWall.organisation_id == org.id)
    #     .where(BusinessWall.status == BWStatus.ACTIVE.value)
    #     .order_by(BusinessWall.created_at.desc())
    # )
    # return session.execute(stmt).scalars().first()


def get_organisation_logo_url(org: Organisation) -> str:
    """Returns the logo URL of the active BusinessWall of the Organisation if
    active, else default logo."""
    if org.is_auto:
        return "/static/img/logo-page-non-officielle.png"
    # Use BusinessWall logo if available
    with contextlib.suppress(NoInspectionAvailable):
        bw = get_active_business_wall_for_organisation(org)
        if bw is not None:
            return bw.logo_image_signed_url()
    return "/static/img/logo-page-non-officielle.png"


def get_organisation_cover_image_url(org: Organisation) -> str:
    """Returns the cover image URL of the active BusinessWall of the Organisation
    if active, else default image."""
    if org.is_auto:
        return "/static/img/transparent-square.png"
    # Use BusinessWall image if available
    with contextlib.suppress(NoInspectionAvailable):
        bw = get_active_business_wall_for_organisation(org)
        if bw is not None:
            return bw.cover_image_signed_url()
    return "/static/img/transparent-square.png"


def get_business_wall_for_user(user: User) -> BusinessWall | None:
    """Get the active BusinessWall for a user (via their organisation)."""
    org = user.organisation
    if not org:
        return None
    return get_active_business_wall_for_organisation(org)


def get_selected_business_wall_for_user(user: User) -> BusinessWall | None:
    """Get the currently selected BusinessWall for the user.

    First checks session for an explicitly selected BW (e.g. via the
    select-bw page), then falls back to the user's organisation BW.
    """
    bw_id: str | None = session.get("bw_id")
    if bw_id:
        try:
            stmt = select(BusinessWall).where(BusinessWall.id == UUID(bw_id))
            bw = db.session.execute(stmt).scalars().one_or_none()
            if bw:
                return bw
        except ValueError:
            pass  # invalid UUID
    return get_business_wall_for_user(user)


def current_business_wall(user: User) -> BusinessWall | None:
    """Get the active BusinessWall for a user (checks session first)."""
    return get_selected_business_wall_for_user(user)


def get_manageable_business_walls_for_user(user: User) -> list[BusinessWall]:
    """Return all BusinessWalls the user can manage.

    Includes BWs owned by the user and BWs where the user has an accepted
    role assignment with management or PR permissions.
    """
    manageable_ids: set[UUID] = set()

    # BWs owned by user
    stmt_owner = select(BusinessWall.id).where(BusinessWall.owner_id == user.id)
    manageable_ids.update(db.session.execute(stmt_owner).scalars().all())

    # BWs where user has an accepted managementrole
    stmt_roles = select(RoleAssignment.business_wall_id).where(
        RoleAssignment.user_id == user.id,
        RoleAssignment.invitation_status == InvitationStatus.ACCEPTED.value,
        RoleAssignment.role_type.in_(
            {
                BWRoleType.BW_OWNER.value,
                BWRoleType.BWMI.value,
                BWRoleType.BWME.value,
            }
        ),
    )
    manageable_ids.update(db.session.execute(stmt_roles).scalars().all())

    if not manageable_ids:
        return []

    stmt = (
        select(BusinessWall)
        .where(BusinessWall.id.in_(manageable_ids))
        .order_by(BusinessWall.name)
    )
    return list(db.session.execute(stmt).scalars().all())


# ---------------------------------------------------------------------------
# Partnership-aware publication authorization
# ---------------------------------------------------------------------------

_ACTIVE_PARTNERSHIP_STATUSES = ("accepted", "active")


def get_validated_client_orgs_for_user(user: User) -> list[Organisation]:
    """Return client Organisations the user's agency is authorized to publish for.

    A client is "validated" when there exists a Partnership between the client's
    BusinessWall and the user's agency BusinessWall, with status ACTIVE (or
    ACCEPTED).
    """
    from app.modules.bw.bw_activation.models import Partnership

    agency_bw = get_business_wall_for_user(user)
    if agency_bw is None:
        warn(f"get_validated_client_orgs_for_user: user {user.id} has no agency_bw")
        return []

    session = inspect(agency_bw).session
    if session is None:
        warn(
            f"get_validated_client_orgs_for_user: no session for agency_bw {agency_bw.id}"
        )
        return []

    agency_bw_id_str = str(agency_bw.id)
    stmt = (
        select(Organisation)
        .join(BusinessWall, Organisation.id == BusinessWall.organisation_id)
        .join(Partnership, Partnership.business_wall_id == BusinessWall.id)
        .where(Partnership.partner_bw_id == agency_bw_id_str)
        .where(Partnership.status.in_(_ACTIVE_PARTNERSHIP_STATUSES))
    )
    results = list(session.execute(stmt).scalars())
    if not results:
        warn(
            f"get_validated_client_orgs_for_user: user {user.id} agency_bw="
            f"{agency_bw_id_str} -> no validated clients found"
        )
    return results


def can_user_publish_for(user: User, publisher_org_id: int) -> bool:
    """Check whether `user` may publish content attributed to `publisher_org_id`.

    A user may always publish for their own organisation. A user whose agency
    has an active Partnership with the target organisation may also publish
    on that organisation's behalf.
    """
    if user.organisation_id and publisher_org_id == user.organisation_id:
        return True

    client_orgs = get_validated_client_orgs_for_user(user)
    result = any(org.id == publisher_org_id for org in client_orgs)
    if not result:
        client_ids = [org.id for org in client_orgs]
        warn(
            f"can_user_publish_for: user {user.id} (org={user.organisation_id}) "
            f"cannot publish for org {publisher_org_id}. "
            f"Validated clients: {client_ids}"
        )
    return result


def get_representing_agency_org_ids_for_client(client_org: Organisation) -> list[int]:
    """Return IDs of agency Organisations that actively represent this client.

    Used when rendering the client's BW to mark press releases as "published
    on our behalf by Agency X", or when rendering the agency's BW to include
    press releases it produced for its clients.
    """
    from app.modules.bw.bw_activation.models import Partnership

    if client_org.bw_id is None:
        return []

    session = inspect(client_org).session
    if session is None:
        return []

    # partner_bw_id is stored as String (no FK) while BusinessWall.id is a UUID.
    # To avoid cross-dialect cast quirks, fetch the matching Partnerships first
    # and resolve each partner BW separately.
    partner_uuids = list(
        session.execute(
            select(Partnership.partner_bw_id)
            .where(Partnership.business_wall_id == client_org.bw_id)
            .where(Partnership.status.in_(_ACTIVE_PARTNERSHIP_STATUSES))
        ).scalars()
    )
    if not partner_uuids:
        return []

    rows = session.execute(
        select(BusinessWall.organisation_id)
        .where(BusinessWall.id.in_(partner_uuids))
        .where(BusinessWall.organisation_id.is_not(None))
    ).scalars()
    return [org_id for org_id in rows if org_id is not None]
