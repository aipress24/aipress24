# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Unit tests for admin/utils.py"""

from __future__ import annotations

from flask_sqlalchemy import SQLAlchemy

from app.enums import OrganisationTypeEnum, RoleEnum
from app.models.auth import KYCProfile, Role, User
from app.models.organisation import Organisation
from app.modules.admin.utils import (
    commit_session,
    gc_organisation,
    get_user_per_email,
    merge_organisation,
    remove_user_organisation,
    set_user_organisation,
    toggle_org_active,
)


class TestGetUserPerEmail:
    """Test suite for get_user_per_email function."""

    def test_returns_user_with_valid_email(self, db: SQLAlchemy) -> None:
        """Test finding an active user by email."""
        user = User(email="test@example.com", active=True)
        db.session.add(user)
        db.session.flush()

        result = get_user_per_email("test@example.com")

        assert result is not None
        assert result.email == "test@example.com"

    def test_returns_user_case_insensitive(self, db: SQLAlchemy) -> None:
        """Test email lookup is case insensitive."""
        user = User(email="Test@Example.COM", active=True)
        db.session.add(user)
        db.session.flush()

        result = get_user_per_email("test@example.com")

        assert result is not None
        assert result.id == user.id

    def test_returns_none_for_empty_email(self, db: SQLAlchemy) -> None:
        """Test empty email returns None."""
        result = get_user_per_email("")
        assert result is None

    def test_returns_none_for_whitespace_email(self, db: SQLAlchemy) -> None:
        """Test whitespace-only email returns None."""
        result = get_user_per_email("   ")
        assert result is None

    def test_returns_none_for_invalid_email_no_at(self, db: SQLAlchemy) -> None:
        """Test email without @ returns None."""
        result = get_user_per_email("invalid-email")
        assert result is None

    def test_returns_none_for_nonexistent_user(self, db: SQLAlchemy) -> None:
        """Test non-existent email returns None."""
        result = get_user_per_email("nonexistent@example.com")
        assert result is None

    def test_returns_none_for_inactive_user(self, db: SQLAlchemy) -> None:
        """Test inactive user returns None."""
        user = User(email="inactive@example.com", active=False)
        db.session.add(user)
        db.session.flush()

        result = get_user_per_email("inactive@example.com")

        assert result is None

    def test_returns_none_for_deleted_user(self, db: SQLAlchemy) -> None:
        """Test deleted user returns None."""
        from arrow import now

        from app.constants import LOCAL_TZ

        user = User(email="deleted@example.com", active=True)
        user.deleted_at = now(LOCAL_TZ)
        db.session.add(user)
        db.session.flush()

        result = get_user_per_email("deleted@example.com")

        assert result is None

    def test_returns_none_for_clone_user(self, db: SQLAlchemy) -> None:
        """Test clone user returns None."""
        user = User(email="clone@example.com", active=True, is_clone=True)
        db.session.add(user)
        db.session.flush()

        result = get_user_per_email("clone@example.com")

        assert result is None

    def test_strips_whitespace_from_email(self, db: SQLAlchemy) -> None:
        """Test whitespace is stripped from email."""
        user = User(email="padded@example.com", active=True)
        db.session.add(user)
        db.session.flush()

        result = get_user_per_email("  padded@example.com  ")

        assert result is not None
        assert result.id == user.id


class TestCommitSession:
    """Test suite for commit_session function."""

    def test_returns_empty_string_on_success(self, db: SQLAlchemy) -> None:
        """Test successful commit returns empty string."""
        result = commit_session(db.session)
        assert result == ""


class TestToggleOrgActive:
    """Test suite for toggle_org_active function."""

    def test_toggles_active_to_inactive(self, db: SQLAlchemy) -> None:
        """Test toggling active org to inactive."""
        org = Organisation(name="Test Org", active=True)
        db.session.add(org)
        db.session.flush()

        toggle_org_active(org)

        assert org.active is False

    def test_toggles_inactive_to_active(self, db: SQLAlchemy) -> None:
        """Test toggling inactive org to active."""
        org = Organisation(name="Test Org", active=False)
        db.session.add(org)
        db.session.flush()

        toggle_org_active(org)

        assert org.active is True


class TestMergeOrganisation:
    """Test suite for merge_organisation function."""

    def test_merges_organisation_changes(self, db: SQLAlchemy) -> None:
        """Test organisation changes are merged."""
        org = Organisation(name="Original Name")
        db.session.add(org)
        db.session.flush()

        org.name = "Updated Name"
        merge_organisation(org)

        # Refresh from database
        db.session.expire(org)
        assert org.name == "Updated Name"


class TestGcOrganisation:
    """Test suite for gc_organisation function."""

    def test_returns_false_for_none(self, db: SQLAlchemy) -> None:
        """Test None organisation returns False."""
        result = gc_organisation(None)
        assert result is False

    def test_returns_false_for_non_auto_org(self, db: SQLAlchemy) -> None:
        """Test non-AUTO organisation returns False."""
        org = Organisation(name="Media Org", type=OrganisationTypeEnum.MEDIA)
        db.session.add(org)
        db.session.flush()

        result = gc_organisation(org)

        assert result is False

    def test_returns_false_for_auto_org_with_members(self, db: SQLAlchemy) -> None:
        """Test AUTO organisation with members returns False."""
        org = Organisation(name="Auto Org", type=OrganisationTypeEnum.AUTO)
        user = User(email="member@example.com", active=True)
        user.organisation = org
        db.session.add_all([org, user])
        db.session.flush()

        result = gc_organisation(org)

        assert result is False

    def test_deletes_empty_auto_org(self, db: SQLAlchemy) -> None:
        """Test empty AUTO organisation is deleted."""
        org = Organisation(name="Empty Auto Org", type=OrganisationTypeEnum.AUTO)
        db.session.add(org)
        db.session.flush()
        org_id = org.id

        result = gc_organisation(org)

        assert result is True
        # Check org is either deleted or marked as deleted
        refreshed_org = db.session.get(Organisation, org_id)
        assert refreshed_org is None or refreshed_org.deleted_at is not None


class TestSetUserOrganisation:
    """Test suite for set_user_organisation function."""

    def test_sets_user_organisation(self, db: SQLAlchemy) -> None:
        """Test setting user's organisation."""
        org = Organisation(name="New Org", type=OrganisationTypeEnum.MEDIA)
        user = User(email="set_org_user@example.com", active=True)
        profile = KYCProfile()
        user.profile = profile
        db.session.add_all([org, user, profile])
        db.session.flush()

        result = set_user_organisation(user, org)

        assert result == ""  # No error
        assert user.organisation_id == org.id

    def test_removes_previous_organisation(self, db: SQLAlchemy) -> None:
        """Test previous organisation is removed."""
        old_org = Organisation(name="Old Org", type=OrganisationTypeEnum.MEDIA)
        new_org = Organisation(name="New Org", type=OrganisationTypeEnum.COM)
        user = User(email="user_prev_org@example.com", active=True)
        profile = KYCProfile()
        user.profile = profile
        user.organisation = old_org
        db.session.add_all([old_org, new_org, user, profile])
        db.session.flush()

        set_user_organisation(user, new_org)

        assert user.organisation_id == new_org.id


class TestRemoveUserOrganisation:
    """Test suite for remove_user_organisation function."""

    def test_removes_user_organisation(self, db: SQLAlchemy) -> None:
        """Test removing user's organisation."""
        org = Organisation(name="Test Org Remove", type=OrganisationTypeEnum.MEDIA)
        user = User(email="user_remove_org@example.com", active=True)
        profile = KYCProfile()
        user.profile = profile
        user.organisation = org
        db.session.add_all([org, user, profile])
        db.session.flush()

        result = remove_user_organisation(user)

        assert result == ""  # No error
        assert user.organisation_id is None

    def test_removes_manager_role(self, db: SQLAlchemy) -> None:
        """Test manager role is removed when leaving organisation."""
        org = Organisation(name="Test Org Manager", type=OrganisationTypeEnum.MEDIA)
        # Get or create the role to avoid UNIQUE constraint issues
        manager_role = (
            db.session.query(Role).filter_by(name=RoleEnum.MANAGER.name).first()
        )
        if not manager_role:
            manager_role = Role(name=RoleEnum.MANAGER.name, description="Manager")
            db.session.add(manager_role)
            db.session.flush()
        user = User(email="manager_rm@example.com", active=True)
        profile = KYCProfile()
        user.profile = profile
        user.organisation = org
        user.roles.append(manager_role)
        db.session.add_all([org, user, profile])
        db.session.flush()

        remove_user_organisation(user)

        assert not user.is_manager


class TestSetUserOrganisationTypes:
    """Test suite for _set_user_profile_organisation with different org types."""

    def test_sets_media_org_profile(self, db: SQLAlchemy) -> None:
        """Test setting MEDIA organisation updates profile correctly."""
        org = Organisation(name="Media Corp", type=OrganisationTypeEnum.MEDIA)
        user = User(email="media_user@example.com", active=True)
        profile = KYCProfile()
        user.profile = profile
        db.session.add_all([org, user, profile])
        db.session.flush()

        set_user_organisation(user, org)

        assert user.profile.info_professionnelle.get("nom_media") == ["Media Corp"]

    def test_sets_agency_org_profile(self, db: SQLAlchemy) -> None:
        """Test setting AGENCY organisation updates profile correctly."""
        org = Organisation(name="Agency Inc", type=OrganisationTypeEnum.AGENCY)
        user = User(email="agency_user@example.com", active=True)
        profile = KYCProfile()
        user.profile = profile
        db.session.add_all([org, user, profile])
        db.session.flush()

        set_user_organisation(user, org)

        assert user.profile.info_professionnelle.get("nom_media") == ["Agency Inc"]

    def test_sets_com_org_profile(self, db: SQLAlchemy) -> None:
        """Test setting COM organisation updates profile correctly."""
        org = Organisation(name="PR Agency", type=OrganisationTypeEnum.COM)
        user = User(email="com_user@example.com", active=True)
        profile = KYCProfile()
        user.profile = profile
        db.session.add_all([org, user, profile])
        db.session.flush()

        set_user_organisation(user, org)

        assert user.profile.info_professionnelle.get("nom_agence_rp") == "PR Agency"

    def test_sets_other_org_profile(self, db: SQLAlchemy) -> None:
        """Test setting OTHER organisation updates profile correctly."""
        org = Organisation(name="Other Org", type=OrganisationTypeEnum.OTHER)
        user = User(email="other_user@example.com", active=True)
        profile = KYCProfile()
        user.profile = profile
        db.session.add_all([org, user, profile])
        db.session.flush()

        set_user_organisation(user, org)

        assert user.profile.info_professionnelle.get("nom_orga") == "Other Org"

    def test_sets_auto_org_profile(self, db: SQLAlchemy) -> None:
        """Test setting AUTO organisation updates profile correctly."""
        org = Organisation(name="Auto Org", type=OrganisationTypeEnum.AUTO)
        user = User(email="auto_user@example.com", active=True)
        profile = KYCProfile()
        user.profile = profile
        db.session.add_all([org, user, profile])
        db.session.flush()

        set_user_organisation(user, org)

        assert user.profile.info_professionnelle.get("nom_orga") == "Auto Org"


class TestGcAllAutoOrganisations:
    """Test suite for gc_all_auto_organisations function."""

    def test_deletes_empty_auto_orgs(self, db: SQLAlchemy) -> None:
        """Test deletes all empty AUTO organisations."""
        from app.modules.admin.utils import gc_all_auto_organisations

        # Create empty AUTO organisations
        org1 = Organisation(name="Empty Auto 1", type=OrganisationTypeEnum.AUTO)
        org2 = Organisation(name="Empty Auto 2", type=OrganisationTypeEnum.AUTO)
        db.session.add_all([org1, org2])
        db.session.flush()

        result = gc_all_auto_organisations()

        assert result >= 2

    def test_preserves_auto_orgs_with_members(self, db: SQLAlchemy) -> None:
        """Test preserves AUTO organisations with members."""
        from app.modules.admin.utils import gc_all_auto_organisations

        org = Organisation(name="Auto With Member", type=OrganisationTypeEnum.AUTO)
        user = User(email="member_auto@example.com", active=True)
        user.organisation = org
        db.session.add_all([org, user])
        db.session.flush()
        org_id = org.id

        gc_all_auto_organisations()

        # Organisation should still exist
        refreshed_org = db.session.get(Organisation, org_id)
        assert refreshed_org is not None
        assert refreshed_org.deleted_at is None

    def test_preserves_non_auto_orgs(self, db: SQLAlchemy) -> None:
        """Test preserves non-AUTO empty organisations."""
        from app.modules.admin.utils import gc_all_auto_organisations

        org = Organisation(name="Media Empty", type=OrganisationTypeEnum.MEDIA)
        db.session.add(org)
        db.session.flush()
        org_id = org.id

        gc_all_auto_organisations()

        # Organisation should still exist
        refreshed_org = db.session.get(Organisation, org_id)
        assert refreshed_org is not None
        assert refreshed_org.deleted_at is None


class TestDeleteFullOrganisation:
    """Test suite for delete_full_organisation function."""

    def test_removes_all_members(self, db: SQLAlchemy) -> None:
        """Test all members are removed from organisation."""
        from app.modules.admin.utils import delete_full_organisation

        org = Organisation(name="Org To Delete", type=OrganisationTypeEnum.MEDIA)
        user1 = User(email="delete_member1@example.com", active=True)
        user2 = User(email="delete_member2@example.com", active=True)
        profile1 = KYCProfile()
        profile2 = KYCProfile()
        user1.profile = profile1
        user2.profile = profile2
        user1.organisation = org
        user2.organisation = org
        db.session.add_all([org, user1, user2, profile1, profile2])
        db.session.flush()

        delete_full_organisation(org)

        assert user1.organisation_id is None
        assert user2.organisation_id is None

    def test_marks_organisation_as_deleted(self, db: SQLAlchemy) -> None:
        """Test organisation is marked as deleted."""
        from app.modules.admin.utils import delete_full_organisation

        org = Organisation(name="Org Mark Deleted", type=OrganisationTypeEnum.COM)
        db.session.add(org)
        db.session.flush()

        delete_full_organisation(org)

        assert org.deleted_at is not None
        assert org.active is False

    def test_removes_leader_role_from_members(self, db: SQLAlchemy) -> None:
        """Test leader role is removed from members."""
        from app.modules.admin.utils import delete_full_organisation

        org = Organisation(name="Org Leader Delete", type=OrganisationTypeEnum.MEDIA)
        leader_role = (
            db.session.query(Role).filter_by(name=RoleEnum.LEADER.name).first()
        )
        if not leader_role:
            leader_role = Role(name=RoleEnum.LEADER.name, description="Leader")
            db.session.add(leader_role)
            db.session.flush()

        user = User(email="leader_delete@example.com", active=True)
        profile = KYCProfile()
        user.profile = profile
        user.organisation = org
        user.roles.append(leader_role)
        db.session.add_all([org, user, profile])
        db.session.flush()

        delete_full_organisation(org)

        assert not user.is_leader
