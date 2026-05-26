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
from app.models.auth import BW_TYPE_FONCTION_SOURCES
from app.modules.admin.utils import Organisation
from app.modules.bw.bw_activation.bw_invitation import BW_ROLE_TYPE_LABEL
from app.modules.bw.bw_activation.models import (
    BusinessWall,
    BWRoleType,
    InvitationStatus,
    RoleAssignment,
)
from app.modules.bw.bw_activation.models.business_wall import BWStatus, BWType
from app.modules.bw.bw_activation.utils import DASHBOARD_ACCESS_ROLES

# Loose dict shape used to carry KYC-shaped data from the view layer
# to templates. Includes `list[str]` so step 2 can expose the user's
# full list of available fonctions for the autocomplete datalist
# (bug #0107).
StdDict = dict[str, str | int | float | bool | None | list[str]]

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
    # pyrefly: ignore [no-matching-overload]
    data.update(
        {
            "first_name": user.first_name,
            "last_name": user.last_name,
            "phone": user.tel_mobile,
            "email": user.email,
            "fonction": user.metier_fonction_for_bw(bw_type),
            # Bug #0107: the default value is the first item of an
            # unordered KYC list, which is often misleading (e.g. "chef
            # de projet média" for a "rédacteur en chef"). Expose the
            # full list of relevant fonctions so the template can offer
            # autocomplete on the input.
            "fonctions_disponibles": _fonctions_disponibles_for_bw(user, bw_type),
            "allow_activation": (org and org.is_auto_or_inactive),
        }
    )
    return data


def _fonctions_disponibles_for_bw(user: User, bw_type: str | None) -> list[str]:
    """Return all KYC fonctions relevant for a given BW type, deduped.

    Used by the step-2 Fonction/Titre input to offer the user every
    fonction they have in their KYC profile (so they can switch from
    the arbitrary default without having to retype it).
    """
    profile = getattr(user, "profile", None)
    if profile is None:
        return []
    sources = BW_TYPE_FONCTION_SOURCES.get(bw_type or "")
    if not sources:
        return list(profile.toutes_fonctions)
    seen: set[str] = set()
    out: list[str] = []
    for attr in sources:
        for value in getattr(profile, attr, None) or []:
            if value and value not in seen:
                seen.add(value)
                out.append(value)
    return out


def guess_best_bw_type(user: User) -> BWType:
    profile = user.profile
    # `user.profile` may be None for freshly-created users that
    # haven't filled the KYC wizard yet. Since #0117 lifted the
    # « must have an organisation » gate, those users now reach
    # `index()` and trigger this helper. Default to `MEDIA` like
    # the malformed-profile-code path below.
    if profile is None:
        return BWType.MEDIA  # type: ignore[invalid-return-type]
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


def resolve_user_bw_name(user: User, fallback: str = "inconnue") -> str:
    """Best-effort name of the BW a user publishes for.

    Prefer the active BW's `name_safe` (media-group case: organisation
    is « LVMH », BW is « Les Échos » — readers expect the media name).
    Falls back to the organisation's own name, then `fallback`.
    """
    org = user.organisation
    if org is None:
        return fallback
    active_bw = get_active_business_wall_for_organisation(org)
    if active_bw is not None and active_bw.name_safe:
        return active_bw.name_safe
    return org.name or fallback


def is_organisation_an_agency(org: Organisation) -> bool:
    result: bool = False
    bw = get_active_business_wall_for_organisation(org)
    if org.bw_active == "media" and bw:
        if "Agence de presse" in bw.type_entreprise_media:
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

    Checks the user for an explicitly selected BW, then the session,
    then falls back to the user's organisation default BW.
    """
    # 1. Check user profile
    bw_id = user.selected_bw_id
    if bw_id:
        stmt = select(BusinessWall).where(BusinessWall.id == bw_id)
        bw = db.session.execute(stmt).scalars().one_or_none()
        if bw:
            return bw

    # 2. Check session fallback
    bw_id_sess: str | None = session.get("bw_id")
    if bw_id_sess:
        try:
            stmt = select(BusinessWall).where(BusinessWall.id == UUID(bw_id_sess))
            bw = db.session.execute(stmt).scalars().one_or_none()
            if bw:
                return bw
        except ValueError:
            pass  # invalid UUID

    # 3. Fallback to org
    return get_business_wall_for_user(user)


def current_business_wall(user: User) -> BusinessWall | None:
    """Get the active BusinessWall for a user (checks session first)."""
    return get_selected_business_wall_for_user(user)


def get_user_rights_on_bw(user: User, bw: BusinessWall) -> list[str]:
    """Return a list of human-readable rights/actions for the user on this BW."""

    MISSION_LABELS = {
        "press_release": "Publier des communiqués de presse",
        "events": "Publier des événements",
        "missions": "Publier des Missions",
        "projects": "Publier des Projets",
        "internships": "Publier des offres de stage",
        "apprenticeships": "Publier des offres d'alternance",
        "doctoral": "Publier des offres de convention doctorale",
    }

    rights = []
    seen_roles = set()
    seen_missions = set()

    # 1. Check if owner
    if bw.owner_id == user.id:
        rights.append(f"Propriétaire ({BW_ROLE_TYPE_LABEL['BW_OWNER']})")
        seen_roles.add(BWRoleType.BW_OWNER.value)

    # 2. Check RoleAssignments
    if bw.role_assignments:
        for assignment in bw.role_assignments:
            if (
                assignment.user_id == user.id
                and assignment.invitation_status == InvitationStatus.ACCEPTED.value
            ):
                if assignment.role_type not in seen_roles:
                    role_label = BW_ROLE_TYPE_LABEL.get(
                        assignment.role_type, assignment.role_type
                    )
                    rights.append(f"Rôle : {role_label}")
                    seen_roles.add(assignment.role_type)

                # Granular permissions for PR Managers
                if assignment.role_type in (
                    BWRoleType.BWPRI.value,
                    BWRoleType.BWPRE.value,
                ):
                    for perm in assignment.permissions:
                        if (
                            perm.is_granted
                            and perm.permission_type not in seen_missions
                        ):
                            mission_label = MISSION_LABELS.get(
                                perm.permission_type, perm.permission_type
                            )
                            rights.append(f"Mission : {mission_label}")
                            seen_missions.add(perm.permission_type)

    return rights


def get_manageable_business_walls_for_user(user: User) -> list[BusinessWall]:
    """Return all BusinessWalls the user can manage *or publish for*.

    Includes :

    1. BWs owned by the user.
    2. BWs where the user has an accepted role in DASHBOARD_ACCESS_ROLES
       (BW_OWNER / BWMi / BWMe) — the strict management subset.
    3. Ticket #0166 — client BWs reachable through an active Partnership
       between the user's organisation BWs (agency side) and a client
       BW. Without this branch, a PR Agency owner (Alfred Delarue's
       case) only saw their own agency BW in /BW/select-bw and could
       never switch into a client's surface to publish CPs / events.
    """
    from app.modules.bw.bw_activation.models import Partnership

    manageable_ids: set[UUID] = set()

    # 1) BWs owned by user
    stmt_owner = select(BusinessWall.id).where(BusinessWall.owner_id == user.id)
    manageable_ids.update(db.session.execute(stmt_owner).scalars().all())

    # 2) BWs where user has an accepted management role. Use the shared
    # DASHBOARD_ACCESS_ROLES constant so this list stays in sync with the
    # dashboard route guard / template visibility check.
    stmt_roles = select(RoleAssignment.business_wall_id).where(
        RoleAssignment.user_id == user.id,
        RoleAssignment.invitation_status == InvitationStatus.ACCEPTED.value,
        RoleAssignment.role_type.in_(DASHBOARD_ACCESS_ROLES),
    )
    manageable_ids.update(db.session.execute(stmt_roles).scalars().all())

    # 3) Client BWs reachable via active PR partnerships. The user's
    # agency may own several BWs (rare but possible — historical
    # clutter / brand variants), so union across all of them.
    if user.organisation_id:
        agency_bw_id_strs = [
            str(bw_id)
            for bw_id in db.session.execute(
                select(BusinessWall.id).where(
                    BusinessWall.organisation_id == user.organisation_id
                )
            ).scalars()
        ]
        if agency_bw_id_strs:
            stmt_partnerships = select(Partnership.business_wall_id).where(
                Partnership.partner_bw_id.in_(agency_bw_id_strs),
                Partnership.status.in_(_ACTIVE_PARTNERSHIP_STATUSES),
            )
            manageable_ids.update(
                db.session.execute(stmt_partnerships).scalars().all()
            )

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
    BusinessWall and any of the agency organisation's BusinessWalls, with status
    ACTIVE (or ACCEPTED).

    Note: an agency organisation may have several BWs (one per brand, or
    historical clutter from re-creations). Partnerships are stored per-BW. We
    union across all BWs of the user's organisation so the user sees every
    client the agency may publish for, regardless of which specific BW the
    partnership was negotiated against. (Bug 0124-B: previously this query
    only considered `Organisation.bw_id` — the single "active" BW — so clients
    tied to other BWs of the same org were silently dropped.)
    """
    from app.modules.bw.bw_activation.models import Partnership

    if not user.organisation_id:
        warn(f"get_validated_client_orgs_for_user: user {user.id} has no organisation")
        return []

    session = db.session

    # All BWs belonging to the user's organisation (agent side).
    agency_bw_ids = list(
        session.execute(
            select(BusinessWall.id).where(
                BusinessWall.organisation_id == user.organisation_id
            )
        ).scalars()
    )
    if not agency_bw_ids:
        warn(
            f"get_validated_client_orgs_for_user: user {user.id} (org="
            f"{user.organisation_id}) has no BusinessWall on the agency side"
        )
        return []

    # `Partnership.partner_bw_id` is a String column (no FK) holding a UUID
    # string — compare as strings to avoid cross-dialect cast quirks.
    agency_bw_id_strs = [str(bw_id) for bw_id in agency_bw_ids]

    stmt = (
        select(Organisation)
        .join(BusinessWall, Organisation.id == BusinessWall.organisation_id)
        .join(Partnership, Partnership.business_wall_id == BusinessWall.id)
        .where(Partnership.partner_bw_id.in_(agency_bw_id_strs))
        .where(Partnership.status.in_(_ACTIVE_PARTNERSHIP_STATUSES))
        .distinct()
    )
    results = list(session.execute(stmt).scalars())
    if not results:
        warn(
            f"get_validated_client_orgs_for_user: user {user.id} (org="
            f"{user.organisation_id}, {len(agency_bw_id_strs)} agency BW(s)) "
            f"-> no validated clients found"
        )
    return results


def can_user_publish_for(user: User, publisher_org_id: int) -> bool:
    """Check whether `user` may publish content attributed to `publisher_org_id`.

    A user may always publish for their own organisation. A user whose agency
    has an active Partnership with the target organisation may also publish
    on that organisation's behalf, or if the user has an explicit PR role assignment.
    """
    if user.organisation_id and publisher_org_id == user.organisation_id:
        return True

    stmt = (
        select(BusinessWall.id)
        .join(RoleAssignment, RoleAssignment.business_wall_id == BusinessWall.id)
        .where(BusinessWall.organisation_id == publisher_org_id)
        .where(RoleAssignment.user_id == user.id)
        .where(RoleAssignment.invitation_status == InvitationStatus.ACCEPTED.value)
        .where(
            RoleAssignment.role_type.in_(
                (
                    BWRoleType.BWPRI.value,
                    BWRoleType.BWPRE.value,
                    BWRoleType.BW_OWNER.value,
                )
            )
        )
    )
    if db.session.execute(stmt).first():
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
