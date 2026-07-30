# Copyright (c) 2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Integration test for BW cancellation and organisation invitations cleanup."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING
from unittest.mock import patch

from sqlalchemy import select

from app.models.auth import KYCProfile, User
from app.models.invitation import Invitation
from app.models.organisation import Organisation
from app.modules.admin.invitations import add_invited_users
from app.modules.admin.org_email_utils import change_invitations_emails
from app.modules.bw.bw_activation.bw_cancellation import close_business_wall_locally
from app.modules.bw.bw_activation.models import (
    EXTERNAL_ROLES,
    BusinessWall,
    BWStatus,
    RoleAssignment,
)
from app.modules.bw.bw_activation.models.role import BWRoleType, InvitationStatus
from app.modules.preferences.views.invitations import InvitationsView

if TYPE_CHECKING:
    from flask import Flask
    from sqlalchemy.orm import Session


def test_invitations_tied_to_bw_are_cleared_on_cancellation(
    app: Flask, db_session: Session
):
    with app.test_request_context():
        user = User(email=f"owner_{uuid.uuid4().hex[:6]}@example.com", active=True)
        db_session.add(user)
        org = Organisation(name="Test Org Cancellation")
        db_session.add(org)
        db_session.flush()

        bw = BusinessWall(
            name="Test BW Cancellation",
            bw_type="BWMi",
            owner_id=user.id,
            payer_id=user.id,
            organisation_id=org.id,
            status=BWStatus.ACTIVE.value,
        )
        db_session.add(bw)
        db_session.flush()

        # Add invitations tied to BW
        add_invited_users("user1@example.com", org.id, bw_id=bw.id)
        # Add invitation without BW (org standalone)
        add_invited_users("standalone@example.com", org.id, bw_id=None)
        db_session.flush()

        bw_invites = (
            db_session.query(Invitation).filter_by(business_wall_id=bw.id).all()
        )
        assert len(bw_invites) == 1
        assert bw_invites[0].email == "user1@example.com"

        # Close BW locally
        res = close_business_wall_locally(bw, commit=False)
        assert res["success"] is True
        assert res["cleared_invitations_count"] == 1
        db_session.flush()

        # BW-tied invitation should be deleted
        remaining_bw_invites = (
            db_session.query(Invitation).filter_by(business_wall_id=bw.id).all()
        )
        assert len(remaining_bw_invites) == 0

        # Standalone org invitation should still exist
        standalone_invites = (
            db_session.query(Invitation).filter_by(organisation_id=org.id).all()
        )
        assert len(standalone_invites) == 1
        assert standalone_invites[0].email == "standalone@example.com"


@patch("app.modules.admin.invitations.send_invitation_mails")
def test_change_invitations_emails_stores_bw_id(
    mock_send_mails, app: Flask, db_session: Session
):
    with app.test_request_context():
        user = User(email=f"owner_{uuid.uuid4().hex[:6]}@example.com", active=True)
        db_session.add(user)
        org = Organisation(name="Test Org Change Mails")
        db_session.add(org)
        db_session.flush()

        bw = BusinessWall(
            name="Test BW Change Mails",
            bw_type="BWMi",
            owner_id=user.id,
            payer_id=user.id,
            organisation_id=org.id,
            status=BWStatus.ACTIVE.value,
        )
        db_session.add(bw)
        db_session.flush()

        change_invitations_emails(
            org, "invited1@example.com invited2@example.com", bw_id=bw.id
        )
        db_session.flush()

        invites = db_session.query(Invitation).filter_by(organisation_id=org.id).all()
        assert len(invites) == 2
        for inv in invites:
            assert inv.business_wall_id == bw.id


def test_join_organisation_creates_role_assignment(app: Flask, db_session: Session):
    with app.test_request_context():
        owner = User(email=f"owner_{uuid.uuid4().hex[:6]}@example.com", active=True)
        db_session.add(owner)
        org = Organisation(name="Test Org Role Assignment")
        db_session.add(org)
        db_session.flush()

        bw = BusinessWall(
            name="Test BW Role Assignment",
            bw_type="BWMi",
            owner_id=owner.id,
            payer_id=owner.id,
            organisation_id=org.id,
            status=BWStatus.ACTIVE.value,
        )
        db_session.add(bw)
        org.bw_id = bw.id
        db_session.flush()

        invited_user = User(
            email=f"invited_{uuid.uuid4().hex[:6]}@example.com",
            active=True,
        )
        db_session.add(invited_user)
        db_session.flush()
        db_session.add(KYCProfile(user_id=invited_user.id))
        db_session.flush()

        add_invited_users(invited_user.email, org.id, bw_id=bw.id)
        db_session.flush()

        view = InvitationsView()
        view._join_organisation(invited_user, str(org.id))
        db_session.flush()

        assert invited_user.organisation_id == org.id

        role_assignment = db_session.scalar(
            select(RoleAssignment).where(
                RoleAssignment.business_wall_id == bw.id,
                RoleAssignment.user_id == invited_user.id,
            )
        )
        assert role_assignment is not None
        assert role_assignment.role_type == ""
        assert role_assignment.invitation_status == "accepted"

        # Teardown because _join_organisation commits.
        # Order matters: these are bulk deletes (no ORM cascade), so each
        # table must go before the one it references. `aut_user.organisation_id`
        # points at the org, hence User before Organisation — PostgreSQL
        # enforces that FK, SQLite (foreign_keys OFF) silently tolerates it.
        db_session.query(RoleAssignment).delete()
        db_session.query(BusinessWall).delete()
        db_session.query(KYCProfile).delete()
        db_session.query(User).delete()
        db_session.query(Organisation).delete()
        db_session.commit()


def test_external_partner_roles_excluded_from_bw_members(
    app: Flask, db_session: Session
):
    with app.test_request_context():
        owner = User(email=f"owner_{uuid.uuid4().hex[:6]}@example.com", active=True)
        db_session.add(owner)
        org = Organisation(name="Test Org External Excluded")
        db_session.add(org)
        db_session.flush()

        bw = BusinessWall(
            name="Test BW External Excluded",
            bw_type="BWMi",
            owner_id=owner.id,
            payer_id=owner.id,
            organisation_id=org.id,
            status=BWStatus.ACTIVE.value,
        )
        db_session.add(bw)
        db_session.flush()

        external_user = User(
            email=f"external_{uuid.uuid4().hex[:6]}@example.com",
            active=True,
        )
        db_session.add(external_user)
        db_session.flush()

        # Add external BWMe role assignment
        db_session.add(
            RoleAssignment(
                business_wall_id=bw.id,
                user_id=external_user.id,
                role_type=BWRoleType.BWME.value,
                invitation_status=InvitationStatus.ACCEPTED.value,
            )
        )
        db_session.flush()

        # Calculate members as done in stage_b3.py
        members_set: set[User] = set()
        if bw.owner_id:
            bw_owner = db_session.get(User, bw.owner_id)
            if bw_owner:
                members_set.add(bw_owner)

        external_user_ids = set(
            db_session.scalars(
                select(RoleAssignment.user_id)
                .where(RoleAssignment.business_wall_id == bw.id)
                .where(
                    RoleAssignment.invitation_status == InvitationStatus.ACCEPTED.value
                )
                .where(RoleAssignment.role_type.in_(EXTERNAL_ROLES))
            ).all()
        )

        members = [
            u
            for u in members_set
            if u.id not in external_user_ids or u.id == bw.owner_id
        ]
        assert len(members) == 1
        assert owner in members
        assert external_user not in members
