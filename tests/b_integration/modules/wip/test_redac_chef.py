# Copyright (c) 2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Who counts as the rédac chef of a media (`app.modules.wip.redac_chef`)."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from app.models.auth import KYCProfile, User
from app.models.organisation import Organisation
from app.modules.bw.bw_activation.models import (
    BusinessWall,
    BWRoleType,
    BWStatus,
    InvitationStatus,
    RoleAssignment,
)
from app.modules.wip.redac_chef import is_redac_chef_of_org, redac_chef_media_id

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


def _org(db_session: Session, name: str) -> Organisation:
    org = Organisation(name=f"{name} {uuid.uuid4().hex[:8]}")
    db_session.add(org)
    db_session.flush()
    return org


def _journalist(db_session: Session, org: Organisation, profile_code: str) -> User:
    user = User(email=f"j-{uuid.uuid4().hex[:8]}@example.com", active=True)
    user.organisation = org
    user.organisation_id = org.id
    user.profile = KYCProfile(profile_code=profile_code)
    db_session.add(user)
    db_session.flush()
    return user


def _active_bw(db_session: Session, org: Organisation, owner: User) -> BusinessWall:
    bw = BusinessWall(
        bw_type="media",
        status=BWStatus.ACTIVE.value,
        is_free=True,
        owner_id=owner.id,
        payer_id=owner.id,
        organisation_id=org.id,
    )
    db_session.add(bw)
    db_session.flush()
    return bw


class TestIsRedacChefOfOrg:
    def test_a_director_of_the_media_qualifies(self, db_session: Session):
        media = _org(db_session, "Media")
        director = _journalist(db_session, media, "PM_DIR")

        assert is_redac_chef_of_org(director, media.id)

    def test_a_director_elsewhere_does_not(self, db_session: Session):
        """The KYC title alone says nothing about which media."""
        media = _org(db_session, "Media")
        other = _org(db_session, "Other")
        director = _journalist(db_session, other, "PM_DIR")

        assert not is_redac_chef_of_org(director, media.id)

    def test_a_business_wall_manager_of_the_media_qualifies(self, db_session: Session):
        media = _org(db_session, "Media")
        owner = _journalist(db_session, media, "PM_JR_CP_SAL")
        bw = _active_bw(db_session, media, owner)
        manager = _journalist(db_session, _org(db_session, "Agency"), "PM_JR_CP_SAL")
        db_session.add(
            RoleAssignment(
                business_wall_id=bw.id,
                user_id=manager.id,
                role_type=BWRoleType.BWMI.value,
                invitation_status=InvitationStatus.ACCEPTED.value,
            )
        )
        db_session.flush()

        assert is_redac_chef_of_org(manager, media.id)

    def test_a_staff_journalist_does_not(self, db_session: Session):
        media = _org(db_session, "Media")
        journalist = _journalist(db_session, media, "PM_JR_CP_SAL")

        assert not is_redac_chef_of_org(journalist, media.id)


class TestRedacChefMediaId:
    def test_it_is_the_director_s_own_media(self, db_session: Session):
        media = _org(db_session, "Media")
        director = _journalist(db_session, media, "PM_DIR")

        assert redac_chef_media_id(director) == media.id

    def test_a_staff_journalist_has_none(self, db_session: Session):
        journalist = _journalist(db_session, _org(db_session, "Media"), "PM_JR_CP_SAL")

        assert redac_chef_media_id(journalist) is None
