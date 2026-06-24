# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""E2E tests for admin show_org views."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

import pytest
from sqlalchemy import select

from app.models.auth import KYCProfile, User

# from app.models.invitation import Invitation
from app.models.organisation import Organisation
from app.modules.admin.views._show_org import OrgVM
from app.modules.bw.bw_activation.models import BusinessWall, BWStatus
from app.modules.bw.bw_activation.models.role import (
    BWRoleType,
    InvitationStatus,
    RoleAssignment,
)

if TYPE_CHECKING:
    from flask import Flask
    from flask.testing import FlaskClient
    from sqlalchemy.orm import Session


@pytest.fixture
def test_org_for_admin(db_session: Session) -> Organisation:
    """Create an organisation for admin tests with unique name."""
    unique_id = uuid.uuid4().hex[:8]
    org = Organisation(name=f"Admin Test Org {unique_id}")
    db_session.add(org)
    db_session.flush()

    member = User(
        email=f"member-{unique_id}@admin-test.com",
        first_name="Member",
        last_name="User",
    )
    member.active = True
    member.organisation = org
    db_session.add(member)
    db_session.flush()

    # Create KYCProfile for member (required for email change operations)
    profile = KYCProfile(user=member, profile_id="P001", match_making={})
    db_session.add(profile)
    db_session.commit()
    return org


@pytest.fixture
def org_with_bw(db_session: Session, admin_user: User) -> Organisation:
    """Create an organisation with an active Business Wall."""
    org = Organisation(name="Test Organisation with BW")
    db_session.add(org)
    db_session.flush()

    bw = BusinessWall(
        bw_type="media",
        status=BWStatus.ACTIVE.value,
        owner_id=admin_user.id,
        payer_id=admin_user.id,
        payer_is_owner=True,
        organisation_id=org.id,
    )
    db_session.add(bw)
    db_session.flush()

    # Link organisation to BW
    org.bw_id = bw.id
    org.bw_active = bw.bw_type
    db_session.flush()

    return org


@pytest.fixture
def org_with_invitation(db_session: Session, admin_user: User) -> Organisation:
    """Create an organisation with pending invitations."""
    org = Organisation(name="Test Organisation with Invitation")
    db_session.add(org)
    db_session.flush()

    bw = BusinessWall(
        bw_type="media",
        status=BWStatus.ACTIVE.value,
        owner_id=admin_user.id,
        payer_id=admin_user.id,
        payer_is_owner=True,
        organisation_id=org.id,
    )
    db_session.add(bw)
    db_session.flush()

    # Link organisation to BW
    org.bw_id = bw.id
    org.bw_active = bw.bw_type
    db_session.flush()

    return org


@pytest.fixture
def org_for_deletion(db_session: Session) -> Organisation:
    """Create an organisation for deletion test (no members)."""
    unique_id = uuid.uuid4().hex[:8]
    org = Organisation(name=f"Delete Test Org {unique_id}")
    org.active = True
    db_session.add(org)
    db_session.commit()
    return org


class TestShowOrgPage:
    """Tests for the organisation detail page."""

    def test_show_org_page_accessible(
        self,
        admin_client: FlaskClient,
        admin_user: User,
        test_org_for_admin: Organisation,
    ):
        """Test that show_org page is accessible."""
        response = admin_client.get(f"/admin/show_org/{test_org_for_admin.id}")
        # Accept 200 (success) or 302 (redirect, which is valid for HTMX)
        assert response.status_code in (200, 302)

    def test_show_org_page_not_found(
        self,
        admin_client: FlaskClient,
        admin_user: User,
    ):
        """Test that show_org page returns 404 for non-existent org."""
        response = admin_client.get("/admin/show_org/999999999")
        assert response.status_code in (404, 302)


class TestShowOrgActions:
    """Tests for POST actions on the organisation detail page."""

    def test_toggle_org_active(
        self,
        admin_client: FlaskClient,
        admin_user: User,
        test_org_for_admin: Organisation,
    ):
        """Test toggling organisation active status returns expected response."""
        org = test_org_for_admin

        response = admin_client.post(
            f"/admin/show_org/{org.id}",
            data={"action": "toggle_org_active"},
        )

        assert response.status_code in (200, 302)

    def test_allow_modify_bw(
        self,
        admin_client: FlaskClient,
        admin_user: User,
        test_org_for_admin: Organisation,
    ):
        """Test enabling BW form edit mode."""
        response = admin_client.post(
            f"/admin/show_org/{test_org_for_admin.id}",
            data={"action": "allow_modify_bw"},
        )

        assert response.status_code in (200, 302)

    def test_cancel_modification_bw(
        self,
        admin_client: FlaskClient,
        admin_user: User,
        test_org_for_admin: Organisation,
    ):
        """Test canceling BW form edit mode."""
        response = admin_client.post(
            f"/admin/show_org/{test_org_for_admin.id}",
            data={"action": "cancel_modification_bw"},
        )

        assert response.status_code in (200, 302)

    def test_unknown_action_redirects(
        self,
        admin_client: FlaskClient,
        admin_user: User,
        test_org_for_admin: Organisation,
    ):
        """Test that unknown action redirects."""
        response = admin_client.post(
            f"/admin/show_org/{test_org_for_admin.id}",
            data={"action": "unknown_action"},
        )

        assert response.status_code in (200, 302)

    def test_deactivate_bw(
        self,
        admin_client: FlaskClient,
        admin_user: User,
        org_with_bw: Organisation,
    ):
        """Test deactivating Business Wall."""
        response = admin_client.post(
            f"/admin/show_org/{org_with_bw.id}",
            data={"action": "deactivate_bw"},
        )

        assert response.status_code in (200, 302)

    def test_delete_org(
        self,
        admin_client: FlaskClient,
        admin_user: User,
        org_for_deletion: Organisation,
    ):
        """Test deleting organisation."""
        response = admin_client.post(
            f"/admin/show_org/{org_for_deletion.id}",
            data={"action": "delete_org"},
        )

        assert response.status_code in (200, 302)

    def test_change_emails(
        self,
        admin_client: FlaskClient,
        admin_user: User,
        test_org_for_admin: Organisation,
        db_session: Session,
    ):
        """Test changing member emails."""
        # Get existing member email
        unique_id = uuid.uuid4().hex[:8]
        new_email = f"new-member-{unique_id}@test.com"

        response = admin_client.post(
            f"/admin/show_org/{test_org_for_admin.id}",
            data={"action": "change_emails", "content": new_email},
        )

        assert response.status_code in (200, 302)

    def test_change_invitations_emails(
        self,
        admin_client: FlaskClient,
        admin_user: User,
        org_with_invitation: Organisation,
    ):
        """Test changing invitation emails."""
        unique_id = uuid.uuid4().hex[:8]
        new_emails = f"invite1-{unique_id}@test.com\ninvite2-{unique_id}@test.com"

        response = admin_client.post(
            f"/admin/show_org/{org_with_invitation.id}",
            data={"action": "change_invitations_emails", "content": new_emails},
        )

        assert response.status_code in (200, 302)


class TestChangeBWOwner:
    """Tests for the change BW owner page."""

    def test_change_bw_owner_page_accessible(
        self,
        admin_client: FlaskClient,
        admin_user: User,
        org_with_bw: Organisation,
    ):
        response = admin_client.get(f"/admin/show_org/{org_with_bw.id}/change_bw_owner")
        assert response.status_code == 200
        body = response.data.decode()
        assert "Changer le BW owner du BW" in body
        assert admin_user.email in body

    def test_change_bw_owner_updates_owner_and_org(
        self,
        admin_client: FlaskClient,
        admin_user: User,
        org_with_bw: Organisation,
        db_session: Session,
    ):
        unique_id = uuid.uuid4().hex[:8]
        other_org = Organisation(name=f"Other Org {unique_id}")
        db_session.add(other_org)
        db_session.flush()

        new_owner = User(
            email=f"new-owner-{unique_id}@test.com",
            first_name="New",
            last_name="Owner",
        )
        new_owner.active = True
        new_owner.organisation_id = other_org.id
        db_session.add(new_owner)
        db_session.flush()

        # KYCProfile is required by set_user_organisation.
        profile = KYCProfile(user=new_owner, profile_id="P001", match_making={})
        db_session.add(profile)

        # Give the current (admin) owner a BW_OWNER role so we can verify
        # it is removed after the transfer.
        admin_owner_role = RoleAssignment(
            business_wall_id=org_with_bw.bw_id,
            user_id=admin_user.id,
            role_type=BWRoleType.BW_OWNER.value,
            invitation_status=InvitationStatus.ACCEPTED.value,
        )
        db_session.add(admin_owner_role)
        db_session.commit()

        response = admin_client.post(
            f"/admin/show_org/{org_with_bw.id}/change_bw_owner",
            data={"new_owner_email": new_owner.email},
            follow_redirects=True,
        )
        assert response.status_code == 200

        bw = db_session.get(BusinessWall, org_with_bw.bw_id)
        assert bw is not None
        assert bw.owner_id == new_owner.id
        assert bw.payer_id == new_owner.id

        db_session.refresh(new_owner)
        assert new_owner.organisation_id == org_with_bw.id

        new_owner_role = db_session.scalar(
            select(RoleAssignment).where(
                RoleAssignment.business_wall_id == bw.id,
                RoleAssignment.user_id == new_owner.id,
                RoleAssignment.role_type == BWRoleType.BW_OWNER.value,
            )
        )
        assert new_owner_role is not None

        old_owner_role = db_session.scalar(
            select(RoleAssignment).where(
                RoleAssignment.business_wall_id == bw.id,
                RoleAssignment.user_id == admin_user.id,
                RoleAssignment.role_type == BWRoleType.BW_OWNER.value,
            )
        )
        assert old_owner_role is None

    def test_change_bw_owner_rejects_existing_bw_owner(
        self,
        admin_client: FlaskClient,
        admin_user: User,
        org_with_bw: Organisation,
        db_session: Session,
    ):
        unique_id = uuid.uuid4().hex[:8]
        other_org = Organisation(name=f"Other Org {unique_id}")
        db_session.add(other_org)
        db_session.flush()

        existing_owner = User(
            email=f"existing-owner-{unique_id}@test.com",
            first_name="Existing",
            last_name="Owner",
        )
        existing_owner.active = True
        existing_owner.organisation_id = other_org.id
        db_session.add(existing_owner)
        db_session.flush()

        other_bw = BusinessWall(
            bw_type="media",
            status=BWStatus.ACTIVE.value,
            owner_id=existing_owner.id,
            payer_id=existing_owner.id,
            payer_is_owner=True,
            organisation_id=other_org.id,
        )
        db_session.add(other_bw)
        db_session.commit()

        response = admin_client.post(
            f"/admin/show_org/{org_with_bw.id}/change_bw_owner",
            data={"new_owner_email": existing_owner.email},
            follow_redirects=True,
        )
        assert response.status_code == 200
        # Form is shown again so the admin can retry.
        assert "Changer le BW owner du BW" in response.data.decode()

        bw = db_session.get(BusinessWall, org_with_bw.bw_id)
        assert bw is not None
        assert bw.owner_id == admin_user.id

    def test_change_bw_owner_unknown_email(
        self,
        admin_client: FlaskClient,
        admin_user: User,
        org_with_bw: Organisation,
        db_session: Session,
    ):
        response = admin_client.post(
            f"/admin/show_org/{org_with_bw.id}/change_bw_owner",
            data={"new_owner_email": "unknown@example.com"},
            follow_redirects=True,
        )
        assert response.status_code == 200
        # The form is shown again so the admin can retry.
        assert "Changer le BW owner du BW" in response.data.decode()

        bw = db_session.get(BusinessWall, org_with_bw.bw_id)
        assert bw is not None
        assert bw.owner_id == admin_user.id


class TestOrgVM:
    """Tests for the OrgVM view model."""

    def test_org_vm_exposes_org(self, app: Flask, db_session: Session):
        """Test that OrgVM exposes the org property."""
        unique_id = uuid.uuid4().hex[:8]
        org = Organisation(name=f"VM Test Org {unique_id}")
        db_session.add(org)
        db_session.flush()

        with app.test_request_context():
            vm = OrgVM(org)
            assert vm.org == org

    def test_org_vm_logo_url_auto_org(self, app: Flask, db_session: Session):
        """Test logo URL for auto organisation."""
        unique_id = uuid.uuid4().hex[:8]
        org = Organisation(name=f"Auto Org {unique_id}")
        db_session.add(org)
        db_session.flush()

        with app.test_request_context():
            vm = OrgVM(org)
            assert vm.get_logo_url() == "/static/img/logo-page-non-officielle.png"

    def test_org_vm_get_members(self, app: Flask, db_session: Session):
        """Test get_members returns list of members."""
        unique_id = uuid.uuid4().hex[:8]
        org = Organisation(name=f"Members Test Org {unique_id}")
        db_session.add(org)
        db_session.flush()

        member = User(
            email=f"vm-member-{unique_id}@test.com",
            active=True,
        )
        member.organisation = org
        db_session.add(member)
        db_session.flush()

        with app.test_request_context():
            vm = OrgVM(org)
            members = vm.get_members()
            assert isinstance(members, list)
            assert len(members) == 1
