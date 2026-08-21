# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Integration tests for organisation contacts tab / user roles."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from app.models.auth import KYCProfile, User
from app.models.organisation import Organisation
from app.modules.bw.bw_activation.models import (
    BusinessWall,
    BWRoleType,
    InvitationStatus,
    RoleAssignment,
)
from app.modules.bw.bw_activation.models.business_wall import BWStatus
from app.modules.swork.views.organisation import (
    OrgMemberVM,
    OrgVM,
)

if TYPE_CHECKING:
    from flask import Flask
    from sqlalchemy.orm import Session


def _user(
    db_session: Session,
    first_name: str = "Jean",
    last_name: str = "Dupont",
    job_title: str = "Journaliste",
) -> User:
    user = User(
        email=f"u-{uuid.uuid4().hex[:8]}@example.com",
        first_name=first_name,
        last_name=last_name,
        active=True,
    )
    user.profile = KYCProfile(profile_label=job_title)
    db_session.add(user)
    db_session.flush()
    return user


def _org_with_bw(db_session: Session, owner: User) -> tuple[Organisation, BusinessWall]:
    org = Organisation(name=f"Org {uuid.uuid4().hex[:6]}")
    db_session.add(org)
    db_session.flush()
    bw = BusinessWall(
        bw_type="media",
        status=BWStatus.ACTIVE.value,
        owner_id=owner.id,
        payer_id=owner.id,
        organisation_id=org.id,
        name=org.name,
    )
    db_session.add(bw)
    db_session.flush()
    org.bw_id = bw.id
    org.bw_active = bw.bw_type
    db_session.flush()
    return org, bw


class TestOrgMemberVM:
    def test_proxies_user_attributes(self, db_session: Session):
        user = _user(
            db_session,
            first_name="Alice",
            last_name="Martin",
            job_title="journaliste",
        )
        vm = OrgMemberVM(
            user,
            role_type="BWMi",
            roles=("BWMi",),
            role_label="BWMi",
            is_external=False,
            is_owner=False,
        )

        assert vm.id == user.id
        assert vm.full_name == "Alice Martin"
        assert vm.job_title == "journaliste"
        assert vm.role_type == "BWMi"
        assert vm.roles == ["BWMi"]
        assert vm.role_label == "BWMi"
        assert vm.is_external is False
        assert vm.is_owner is False
        assert vm.is_bw_manager is True


class TestOrgVMGetMembersMixed:
    def test_mixes_owner_assigned_roles_and_simple_members(
        self, app: Flask, db_session: Session
    ):
        owner = _user(db_session, first_name="Owner", last_name="Alpha")
        internal_mgr = _user(db_session, first_name="Internal", last_name="Beta")
        external_mgr = _user(db_session, first_name="External", last_name="Gamma")
        simple_member = _user(db_session, first_name="Simple", last_name="Delta")

        other_org = Organisation(name="Agence Externe")
        db_session.add(other_org)
        db_session.flush()

        org, bw = _org_with_bw(db_session, owner)
        owner.organisation_id = org.id
        internal_mgr.organisation_id = org.id
        external_mgr.organisation_id = other_org.id
        simple_member.organisation_id = org.id
        db_session.flush()

        db_session.add_all(
            [
                RoleAssignment(
                    business_wall_id=bw.id,
                    user_id=internal_mgr.id,
                    role_type=BWRoleType.BWMI.value,
                    invitation_status=InvitationStatus.ACCEPTED.value,
                    accepted_at=datetime.now(UTC),
                ),
                RoleAssignment(
                    business_wall_id=bw.id,
                    user_id=external_mgr.id,
                    role_type=BWRoleType.BWME.value,
                    invitation_status=InvitationStatus.ACCEPTED.value,
                    accepted_at=datetime.now(UTC),
                ),
            ]
        )
        db_session.flush()

        with app.test_request_context():
            vm = OrgVM(org)
            members = vm.get_members()

            assert len(members) == 4
            member_ids = [m.id for m in members]
            assert member_ids == [
                owner.id,
                internal_mgr.id,
                external_mgr.id,
                simple_member.id,
            ]

            # Owner (not displayed)
            m_owner = members[0]
            assert m_owner.is_owner is True
            assert m_owner.role_type == "BW_OWNER"
            assert m_owner.role_label == ""
            assert m_owner.is_external is False

            # Internal manager
            m_internal = members[1]
            assert m_internal.is_owner is False
            assert m_internal.role_type == "BWMi"
            assert m_internal.role_label == "BW manager interne"
            assert m_internal.is_external is False

            # BWMe (not displayed)
            m_external = members[2]
            assert m_external.is_owner is False
            assert m_external.role_type == "BWMe"
            assert m_external.role_label == ""
            assert m_external.is_external is True

            # member
            m_simple = members[3]
            assert m_simple.is_owner is False
            assert m_simple.role_type == ""
            assert m_simple.role_label == ""
            assert m_simple.is_external is False
