# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Unit tests for models/auth.py User and KYCProfile methods."""

from __future__ import annotations

import pytest
from flask_sqlalchemy import SQLAlchemy

from app.enums import RoleEnum
from app.models.auth import KYCProfile, Role, User
from app.models.organisation import Organisation


def get_or_create_role(db: SQLAlchemy, role_enum: RoleEnum) -> Role:
    """Get existing role or create if not exists."""
    role = db.session.query(Role).filter_by(name=role_enum.name).first()
    if not role:
        role = Role(name=role_enum.name, description=role_enum.value)
        db.session.add(role)
        db.session.flush()
    return role


class TestUserOrganisationName:
    """Test suite for User.organisation_name property."""

    def test_returns_organisation_name(self, db: SQLAlchemy) -> None:
        """Test returns organisation name when user has organisation."""
        org = Organisation(name="Test Org Auth")
        user = User(email="org_name_user@example.com")
        profile = KYCProfile()
        user.profile = profile
        user.organisation = org
        db.session.add_all([org, user, profile])
        db.session.flush()

        assert user.organisation_name == "Test Org Auth"

    def test_returns_empty_when_no_organisation(self, db: SQLAlchemy) -> None:
        """Test returns empty string when user has no organisation."""
        user = User(email="no_org_user@example.com")
        profile = KYCProfile()
        user.profile = profile
        db.session.add_all([user, profile])
        db.session.flush()

        assert user.organisation_name == ""


class TestUserJobTitle:
    """Test suite for User.job_title property."""

    def test_returns_profile_label(self, db: SQLAlchemy) -> None:
        """Test returns profile label from KYCProfile."""
        user = User(email="job_title_user@example.com")
        profile = KYCProfile(profile_label="Senior Developer")
        user.profile = profile
        db.session.add_all([user, profile])
        db.session.flush()

        assert user.job_title == "Senior Developer"

    def test_returns_empty_when_no_label(self, db: SQLAlchemy) -> None:
        """Test returns empty string when profile has no label."""
        user = User(email="no_job_user@example.com")
        profile = KYCProfile()
        user.profile = profile
        db.session.add_all([user, profile])
        db.session.flush()

        assert user.job_title == ""


class TestUserHasRole:
    """Test suite for User.has_role method."""

    def test_has_role_with_role_object(self, db: SQLAlchemy) -> None:
        """Test has_role with Role object."""
        user = User(email="has_role_obj@example.com")
        profile = KYCProfile()
        user.profile = profile
        manager_role = get_or_create_role(db, RoleEnum.MANAGER)
        user.roles.append(manager_role)
        db.session.add_all([user, profile])
        db.session.flush()

        assert user.has_role(manager_role) is True

    def test_has_role_with_role_enum(self, db: SQLAlchemy) -> None:
        """Test has_role with RoleEnum."""
        user = User(email="has_role_enum@example.com")
        profile = KYCProfile()
        user.profile = profile
        leader_role = get_or_create_role(db, RoleEnum.LEADER)
        user.roles.append(leader_role)
        db.session.add_all([user, profile])
        db.session.flush()

        assert user.has_role(RoleEnum.LEADER) is True
        assert user.has_role(RoleEnum.MANAGER) is False

    def test_has_role_with_string(self, db: SQLAlchemy) -> None:
        """Test has_role with string."""
        user = User(email="has_role_str@example.com")
        profile = KYCProfile()
        user.profile = profile
        manager_role = get_or_create_role(db, RoleEnum.MANAGER)
        user.roles.append(manager_role)
        db.session.add_all([user, profile])
        db.session.flush()

        assert user.has_role("MANAGER") is True
        assert user.has_role("LEADER") is False

    def test_has_role_invalid_type_raises_error(self, db: SQLAlchemy) -> None:
        """Test has_role raises ValueError for invalid type."""
        user = User(email="has_role_invalid@example.com")
        profile = KYCProfile()
        user.profile = profile
        db.session.add_all([user, profile])
        db.session.flush()

        with pytest.raises(ValueError):
            user.has_role(123)  # type: ignore


class TestUserAddRole:
    """Test suite for User.add_role method."""

    def test_adds_new_role(self, db: SQLAlchemy) -> None:
        """Test adds role to user."""
        user = User(email="add_role_user@example.com")
        profile = KYCProfile()
        user.profile = profile
        db.session.add_all([user, profile])
        db.session.flush()

        manager_role = get_or_create_role(db, RoleEnum.MANAGER)
        result = user.add_role(manager_role)

        assert result is True
        assert user.has_role(manager_role) is True

    def test_returns_false_if_already_has_role(self, db: SQLAlchemy) -> None:
        """Test returns False if user already has the role."""
        user = User(email="add_role_exists@example.com")
        profile = KYCProfile()
        user.profile = profile
        manager_role = get_or_create_role(db, RoleEnum.MANAGER)
        user.roles.append(manager_role)
        db.session.add_all([user, profile])
        db.session.flush()

        result = user.add_role(manager_role)

        assert result is False


class TestUserRemoveRole:
    """Test suite for User.remove_role method."""

    def test_removes_role_object(self, db: SQLAlchemy) -> None:
        """Test removes role with Role object."""
        user = User(email="remove_role_obj@example.com")
        profile = KYCProfile()
        user.profile = profile
        manager_role = get_or_create_role(db, RoleEnum.MANAGER)
        user.roles.append(manager_role)
        db.session.add_all([user, profile])
        db.session.flush()

        user.remove_role(manager_role)

        assert user.has_role(manager_role) is False

    def test_removes_role_enum(self, db: SQLAlchemy) -> None:
        """Test removes role with RoleEnum."""
        user = User(email="remove_role_enum@example.com")
        profile = KYCProfile()
        user.profile = profile
        leader_role = get_or_create_role(db, RoleEnum.LEADER)
        user.roles.append(leader_role)
        db.session.add_all([user, profile])
        db.session.flush()

        user.remove_role(RoleEnum.LEADER)

        assert user.has_role(RoleEnum.LEADER) is False

    def test_removes_role_string(self, db: SQLAlchemy) -> None:
        """Test removes role with string."""
        user = User(email="remove_role_str@example.com")
        profile = KYCProfile()
        user.profile = profile
        manager_role = get_or_create_role(db, RoleEnum.MANAGER)
        user.roles.append(manager_role)
        db.session.add_all([user, profile])
        db.session.flush()

        user.remove_role("MANAGER")

        assert user.has_role("MANAGER") is False

    def test_invalid_type_raises_error(self, db: SQLAlchemy) -> None:
        """Test remove_role raises ValueError for invalid type."""
        user = User(email="remove_role_invalid@example.com")
        profile = KYCProfile()
        user.profile = profile
        db.session.add_all([user, profile])
        db.session.flush()

        with pytest.raises(ValueError):
            user.remove_role(123)  # type: ignore


class TestUserIsMember:
    """Test suite for User.is_member method."""

    def test_is_member_true(self, db: SQLAlchemy) -> None:
        """Test is_member returns True for organisation member."""
        org = Organisation(name="Member Org Auth")
        user = User(email="is_member_true@example.com")
        profile = KYCProfile()
        user.profile = profile
        user.organisation = org
        db.session.add_all([org, user, profile])
        db.session.flush()

        assert user.is_member(org.id) is True

    def test_is_member_false_different_org(self, db: SQLAlchemy) -> None:
        """Test is_member returns False for different organisation."""
        org1 = Organisation(name="Org 1 Auth")
        org2 = Organisation(name="Org 2 Auth")
        user = User(email="is_member_diff@example.com")
        profile = KYCProfile()
        user.profile = profile
        user.organisation = org1
        db.session.add_all([org1, org2, user, profile])
        db.session.flush()

        assert user.is_member(org2.id) is False

    def test_is_member_false_no_org(self, db: SQLAlchemy) -> None:
        """Test is_member returns False when user has no organisation."""
        org = Organisation(name="No Member Org Auth")
        user = User(email="is_member_no_org@example.com")
        profile = KYCProfile()
        user.profile = profile
        db.session.add_all([org, user, profile])
        db.session.flush()

        assert user.is_member(org.id) is False


class TestUserFirstCommunity:
    """Test suite for User.first_community method."""

    def test_returns_press_media_community(self, db: SQLAlchemy) -> None:
        """Test returns PRESS_MEDIA when user has that role."""
        user = User(email="first_comm_pm@example.com")
        profile = KYCProfile()
        user.profile = profile
        pm_role = get_or_create_role(db, RoleEnum.PRESS_MEDIA)
        user.roles.append(pm_role)
        db.session.add_all([user, profile])
        db.session.flush()

        assert user.first_community() == RoleEnum.PRESS_MEDIA

    def test_returns_press_relations_community(self, db: SQLAlchemy) -> None:
        """Test returns PRESS_RELATIONS when user has that role."""
        user = User(email="first_comm_pr@example.com")
        profile = KYCProfile()
        user.profile = profile
        pr_role = get_or_create_role(db, RoleEnum.PRESS_RELATIONS)
        user.roles.append(pr_role)
        db.session.add_all([user, profile])
        db.session.flush()

        assert user.first_community() == RoleEnum.PRESS_RELATIONS

    def test_raises_error_for_unknown_community(self, db: SQLAlchemy) -> None:
        """Test raises RuntimeError when user has no community role."""
        user = User(email="first_comm_unknown@example.com")
        profile = KYCProfile()
        user.profile = profile
        db.session.add_all([user, profile])
        db.session.flush()

        with pytest.raises(RuntimeError):
            user.first_community()


class TestUserIsManagerIsLeader:
    """Test suite for User.is_manager and is_leader properties."""

    def test_is_manager_true(self, db: SQLAlchemy) -> None:
        """Test is_manager returns True when user has MANAGER role."""
        user = User(email="is_manager_true@example.com")
        profile = KYCProfile()
        user.profile = profile
        manager_role = get_or_create_role(db, RoleEnum.MANAGER)
        user.roles.append(manager_role)
        db.session.add_all([user, profile])
        db.session.flush()

        assert user.is_manager is True

    def test_is_manager_false(self, db: SQLAlchemy) -> None:
        """Test is_manager returns False when user doesn't have MANAGER role."""
        user = User(email="is_manager_false@example.com")
        profile = KYCProfile()
        user.profile = profile
        db.session.add_all([user, profile])
        db.session.flush()

        assert user.is_manager is False

    def test_is_leader_true(self, db: SQLAlchemy) -> None:
        """Test is_leader returns True when user has LEADER role."""
        user = User(email="is_leader_true@example.com")
        profile = KYCProfile()
        user.profile = profile
        leader_role = get_or_create_role(db, RoleEnum.LEADER)
        user.roles.append(leader_role)
        db.session.add_all([user, profile])
        db.session.flush()

        assert user.is_leader is True

    def test_is_leader_false(self, db: SQLAlchemy) -> None:
        """Test is_leader returns False when user doesn't have LEADER role."""
        user = User(email="is_leader_false@example.com")
        profile = KYCProfile()
        user.profile = profile
        db.session.add_all([user, profile])
        db.session.flush()

        assert user.is_leader is False


class TestKYCProfileHasFieldName:
    """Test suite for KYCProfile.has_field_name method."""

    def test_finds_field_in_class(self, db: SQLAlchemy) -> None:
        """Test finds field in KYCProfile class attributes."""
        user = User(email="has_field_class@example.com")
        profile = KYCProfile()
        user.profile = profile
        db.session.add_all([user, profile])
        db.session.flush()

        assert profile.has_field_name("profile_code") is True

    def test_finds_field_in_info_professionnelle(self, db: SQLAlchemy) -> None:
        """Test finds field in info_professionnelle dict."""
        user = User(email="has_field_info@example.com")
        profile = KYCProfile()
        user.profile = profile
        db.session.add_all([user, profile])
        db.session.flush()

        profile.info_professionnelle = {"nom_media": "Test Media"}
        assert profile.has_field_name("nom_media") is True

    def test_finds_field_in_match_making(self, db: SQLAlchemy) -> None:
        """Test finds field in match_making dict."""
        user = User(email="has_field_mm@example.com")
        profile = KYCProfile()
        user.profile = profile
        db.session.add_all([user, profile])
        db.session.flush()

        profile.match_making = {"secteurs": ["Tech"]}
        assert profile.has_field_name("secteurs") is True

    def test_returns_false_for_unknown_field(self, db: SQLAlchemy) -> None:
        """Test returns False for unknown field."""
        user = User(email="has_field_unknown@example.com")
        profile = KYCProfile()
        user.profile = profile
        db.session.add_all([user, profile])
        db.session.flush()

        assert profile.has_field_name("unknown_field_xyz") is False


class TestKYCProfileGetValue:
    """Test suite for KYCProfile.get_value method."""

    def test_gets_class_attribute(self, db: SQLAlchemy) -> None:
        """Test gets value from class attribute."""
        user = User(email="get_value_class@example.com")
        profile = KYCProfile(profile_label="Developer")
        user.profile = profile
        db.session.add_all([user, profile])
        db.session.flush()

        assert profile.get_value("profile_label") == "Developer"

    def test_gets_info_professionnelle_value(self, db: SQLAlchemy) -> None:
        """Test gets value from info_professionnelle dict."""
        user = User(email="get_value_info@example.com")
        profile = KYCProfile()
        user.profile = profile
        db.session.add_all([user, profile])
        db.session.flush()

        profile.info_professionnelle = {"nom_media": "Test Media"}
        assert profile.get_value("nom_media") == "Test Media"

    def test_gets_match_making_value(self, db: SQLAlchemy) -> None:
        """Test gets value from match_making dict."""
        user = User(email="get_value_mm@example.com")
        profile = KYCProfile()
        user.profile = profile
        db.session.add_all([user, profile])
        db.session.flush()

        profile.match_making = {"expertise": "AI"}
        assert profile.get_value("expertise") == "AI"

    def test_gets_info_personnelle_value(self, db: SQLAlchemy) -> None:
        """Test gets value from info_personnelle dict."""
        user = User(email="get_value_perso@example.com")
        profile = KYCProfile()
        user.profile = profile
        db.session.add_all([user, profile])
        db.session.flush()

        profile.info_personnelle = {"bio": "Test bio"}
        assert profile.get_value("bio") == "Test bio"

    def test_gets_business_wall_value(self, db: SQLAlchemy) -> None:
        """Test gets value from business_wall dict."""
        user = User(email="get_value_bw@example.com")
        profile = KYCProfile()
        user.profile = profile
        db.session.add_all([user, profile])
        db.session.flush()

        profile.business_wall = {"trigger_pr": True}
        assert profile.get_value("trigger_pr") is True

    def test_returns_empty_for_unknown(self, db: SQLAlchemy) -> None:
        """Test returns empty string for unknown field."""
        user = User(email="get_value_unknown@example.com")
        profile = KYCProfile()
        user.profile = profile
        db.session.add_all([user, profile])
        db.session.flush()

        assert profile.get_value("unknown_field") == ""


class TestKYCProfileGetFirstValue:
    """Test suite for KYCProfile.get_first_value method."""

    def test_returns_first_from_list(self, db: SQLAlchemy) -> None:
        """Test returns first value from list."""
        user = User(email="get_first_list@example.com")
        profile = KYCProfile()
        user.profile = profile
        db.session.add_all([user, profile])
        db.session.flush()

        profile.info_professionnelle = {"newsrooms": ["First", "Second", "Third"]}
        assert profile.get_first_value("newsrooms") == "First"

    def test_returns_empty_for_empty_list(self, db: SQLAlchemy) -> None:
        """Test returns empty string for empty list."""
        user = User(email="get_first_empty@example.com")
        profile = KYCProfile()
        user.profile = profile
        db.session.add_all([user, profile])
        db.session.flush()

        profile.info_professionnelle = {"newsrooms": []}
        assert profile.get_first_value("newsrooms") == ""

    def test_returns_string_value_as_is(self, db: SQLAlchemy) -> None:
        """Test returns string value directly."""
        user = User(email="get_first_str@example.com")
        profile = KYCProfile()
        user.profile = profile
        db.session.add_all([user, profile])
        db.session.flush()

        profile.info_professionnelle = {"nom_media": "Single Value"}
        assert profile.get_first_value("nom_media") == "Single Value"


class TestKYCProfileGetAllBwTrigger:
    """Test suite for KYCProfile.get_all_bw_trigger method."""

    def test_returns_all_true_triggers(self, db: SQLAlchemy) -> None:
        """Test returns all triggers with True value."""
        profile = KYCProfile(
            business_wall={
                "trigger_pr": True,
                "trigger_media": True,
                "trigger_expert": False,
            }
        )
        result = profile.get_all_bw_trigger()
        assert "trigger_pr" in result
        assert "trigger_media" in result
        assert "trigger_expert" not in result

    def test_returns_empty_for_no_triggers(self, db: SQLAlchemy) -> None:
        """Test returns empty list when no triggers are True."""
        profile = KYCProfile(business_wall={"trigger_pr": False})
        assert profile.get_all_bw_trigger() == []


class TestKYCProfileGetFirstBwTrigger:
    """Test suite for KYCProfile.get_first_bw_trigger method."""

    def test_returns_first_trigger(self, db: SQLAlchemy) -> None:
        """Test returns first trigger with True value."""
        profile = KYCProfile(business_wall={"trigger_pr": True, "trigger_media": True})
        result = profile.get_first_bw_trigger()
        assert result in ["trigger_pr", "trigger_media"]

    def test_returns_empty_for_no_triggers(self, db: SQLAlchemy) -> None:
        """Test returns empty string when no triggers are True."""
        profile = KYCProfile(business_wall={"trigger_pr": False})
        assert profile.get_first_bw_trigger() == ""


class TestKYCProfileSetValue:
    """Test suite for KYCProfile.set_value method."""

    def test_sets_class_attribute(self, db: SQLAlchemy) -> None:
        """Test sets class attribute value."""
        user = User(email="set_value_class@example.com")
        profile = KYCProfile()
        user.profile = profile
        db.session.add_all([user, profile])
        db.session.flush()

        profile.set_value("profile_label", "New Label")
        assert profile.profile_label == "New Label"

    def test_sets_info_professionnelle_value(self, db: SQLAlchemy) -> None:
        """Test sets info_professionnelle dict value."""
        user = User(email="set_value_info@example.com")
        profile = KYCProfile()
        user.profile = profile
        db.session.add_all([user, profile])
        db.session.flush()

        profile.info_professionnelle = {"nom_media": "Old"}
        profile.set_value("nom_media", "New Media")
        assert profile.info_professionnelle["nom_media"] == "New Media"

    def test_sets_match_making_value(self, db: SQLAlchemy) -> None:
        """Test sets match_making dict value."""
        user = User(email="set_value_mm@example.com")
        profile = KYCProfile()
        user.profile = profile
        db.session.add_all([user, profile])
        db.session.flush()

        profile.match_making = {"expertise": "Old"}
        profile.set_value("expertise", "New Expertise")
        assert profile.match_making["expertise"] == "New Expertise"
