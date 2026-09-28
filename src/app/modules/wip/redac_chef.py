# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Who counts as a rédacteur en chef of a media.

A rédac chef receives the sujets sent to their media, and reads every
commande placed for it.
"""

from __future__ import annotations

from sqlalchemy import select

from app.flask.extensions import db

_REDAC_CHEF_PROFILES = frozenset({"PM_DIR", "PM_DIR_INST", "PM_DIR_SYND"})


def is_redac_chef_of_org(user, org_id) -> bool:
    """Bug #0132 pt 1 (Erick, 2026-06-02) : Sujets received by a media
    must only surface for actual rédacteurs en chef, not for every
    journalist at the same org.

    A user qualifies as rédac chef of `org_id` if either :
    - they belong to it and their KYC profile is one of the `PM_DIR*`
      codes (Directeur de la rédaction, Directeur institutionnel,
      Directeur syndicat) ;
    - they hold an ACCEPTED BWMi or BW_OWNER RoleAssignment on the
      media's active BW (the org-management equivalent).
    """
    if user is None or getattr(user, "is_anonymous", False):
        return False
    profile = getattr(user, "profile", None)
    profile_code = getattr(profile, "profile_code", "") or ""
    if profile_code in _REDAC_CHEF_PROFILES and user.organisation_id == org_id:
        return True

    # Lazy imports to keep this module importable without pulling
    # the full BW activation tree during cold start.
    from app.modules.bw.bw_activation.models import (
        BusinessWall,
        BWRoleType,
        InvitationStatus,
    )
    from app.modules.bw.bw_activation.models.business_wall import BWStatus

    bw = db.session.scalars(
        select(BusinessWall).where(
            BusinessWall.organisation_id == org_id,
            BusinessWall.status == BWStatus.ACTIVE.value,
        )
    ).first()
    if bw is None:
        return False
    user_id = getattr(user, "id", None)
    if user_id is None:
        return False
    elevated_roles = {BWRoleType.BWMI.value, BWRoleType.BW_OWNER.value}
    for assignment in bw.role_assignments:
        if (
            assignment.user_id == user_id
            and assignment.invitation_status == InvitationStatus.ACCEPTED.value
            and assignment.role_type in elevated_roles
        ):
            return True
    return False


def redac_chef_media_id(user) -> int | None:
    """The media `user` is rédac chef of, if any."""
    org_id = getattr(user, "organisation_id", None)
    if org_id and is_redac_chef_of_org(user, org_id):
        return org_id
    return None
