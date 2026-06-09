# Copyright (c) 2025, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Ticket #0157: a Business Wall *owner* whose only accepted role is
BWPRi (PR Manager, internal) must NOT reach the BW management
dashboard.

Nina was invited by her boss as BWPRi for their lab's Business Wall
and accepted. BWPRi is not a dashboard role
(`DASHBOARD_ACCESS_ROLES = {BW_OWNER, BWMi, BWMe}`), yet she could
manage the BW. Root cause: `bw_managers_ids` added `bw.owner_id`
*unconditionally* ("usefull in first stage of BW registration"), so
the owner reached management even with only a PR role and a fully
active BW. The fallback must be a bootstrap-only safety net: applied
only while no accepted dashboard manager exists yet.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

import pytest

from app.models.auth import User
from app.models.organisation import Organisation
from app.modules.bw.bw_activation.models import BusinessWall, RoleAssignment
from app.modules.bw.bw_activation.models.role import (
    BWRoleType,
    InvitationStatus,
)
from app.modules.bw.bw_activation.utils import is_bw_manager_or_admin

if TYPE_CHECKING:
    from sqlalchemy.orm import scoped_session


def _email() -> str:
    return f"u_{uuid.uuid4().hex[:8]}@example.com"


@pytest.fixture
def org(db_session: scoped_session) -> Organisation:
    org = Organisation(name="Fake-Laboratoire d'IA & robotique")
    db_session.add(org)
    db_session.flush()
    return org


@pytest.fixture
def nina(db_session: scoped_session, org: Organisation) -> User:
    """Owner of the lab's BW, but functionally only a PR manager."""
    user = User(email=_email(), active=True)
    user.organisation_id = org.id
    db_session.add(user)
    db_session.flush()
    return user


@pytest.fixture
def ernestine(db_session: scoped_session, org: Organisation) -> User:
    """The boss — the real internal manager (BWMi)."""
    user = User(email=_email(), active=True)
    user.organisation_id = org.id
    db_session.add(user)
    db_session.flush()
    return user


@pytest.fixture
def active_bw_owned_by_nina(
    db_session: scoped_session, org: Organisation, nina: User
) -> BusinessWall:
    bw = BusinessWall(
        bw_type="corporate",
        status="active",
        is_free=True,
        owner_id=nina.id,
        payer_id=nina.id,
        organisation_id=org.id,
    )
    db_session.add(bw)
    db_session.flush()
    return bw


def _assign(
    db_session: scoped_session,
    bw: BusinessWall,
    user: User,
    role: BWRoleType,
    status: InvitationStatus = InvitationStatus.ACCEPTED,
) -> None:
    db_session.add(
        RoleAssignment(
            business_wall_id=bw.id,
            user_id=user.id,
            role_type=role.value,
            invitation_status=status.value,
        )
    )
    db_session.flush()


class TestOwnerBwPriDashboardAccess:
    def test_owner_with_only_bwpri_cannot_manage_active_bw(
        self,
        db_session: scoped_session,
        app_context,
        active_bw_owned_by_nina: BusinessWall,
        nina: User,
        ernestine: User,
    ) -> None:
        """#0157: Nina owns the BW record but holds only an accepted
        BWPRi role; Ernestine is the real BWMi. Nina must NOT pass the
        management guard; Ernestine must."""
        _assign(db_session, active_bw_owned_by_nina, nina, BWRoleType.BWPRI)
        _assign(db_session, active_bw_owned_by_nina, ernestine, BWRoleType.BWMI)
        db_session.refresh(active_bw_owned_by_nina)

        assert is_bw_manager_or_admin(ernestine, active_bw_owned_by_nina) is True
        assert is_bw_manager_or_admin(nina, active_bw_owned_by_nina) is False

    def test_owner_keeps_access_during_bootstrap_no_managers_yet(
        self,
        db_session: scoped_session,
        app_context,
        active_bw_owned_by_nina: BusinessWall,
        nina: User,
    ) -> None:
        """Documented intent preserved: while the BW has no accepted
        dashboard manager yet (first stage of registration), the owner
        must still be able to configure it."""
        db_session.refresh(active_bw_owned_by_nina)
        assert is_bw_manager_or_admin(nina, active_bw_owned_by_nina) is True

    def test_owner_with_owner_role_keeps_access(
        self,
        db_session: scoped_session,
        app_context,
        active_bw_owned_by_nina: BusinessWall,
        nina: User,
    ) -> None:
        """A well-formed owner (accepted BW_OWNER RoleAssignment) keeps
        management access through the normal role path."""
        _assign(db_session, active_bw_owned_by_nina, nina, BWRoleType.BW_OWNER)
        db_session.refresh(active_bw_owned_by_nina)
        assert is_bw_manager_or_admin(nina, active_bw_owned_by_nina) is True
