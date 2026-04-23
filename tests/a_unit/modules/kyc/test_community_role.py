# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from app.enums import CommunityEnum, RoleEnum
from app.models.auth import Role, User
from app.modules.kyc.community_role import (
    append_user_role_from_community,
    community_to_role_enum,
    community_to_role_name,
    set_user_role_from_community,
)


def _full_role_map() -> dict[str, Role]:
    return {
        RoleEnum.PRESS_MEDIA.name: Role(name=RoleEnum.PRESS_MEDIA.name),
        RoleEnum.PRESS_RELATIONS.name: Role(name=RoleEnum.PRESS_RELATIONS.name),
        RoleEnum.EXPERT.name: Role(name=RoleEnum.EXPERT.name),
        RoleEnum.TRANSFORMER.name: Role(name=RoleEnum.TRANSFORMER.name),
        RoleEnum.ACADEMIC.name: Role(name=RoleEnum.ACADEMIC.name),
        RoleEnum.MANAGER.name: Role(name=RoleEnum.MANAGER.name),
    }


def test_community_to_role_name_with_enum():
    """Test converting CommunityEnum to role name."""
    assert (
        community_to_role_name(CommunityEnum.PRESS_MEDIA) == RoleEnum.PRESS_MEDIA.name
    )
    assert (
        community_to_role_name(CommunityEnum.COMMUNICANTS)
        == RoleEnum.PRESS_RELATIONS.name
    )
    assert community_to_role_name(CommunityEnum.LEADERS_EXPERTS) == RoleEnum.EXPERT.name
    assert (
        community_to_role_name(CommunityEnum.TRANSFORMERS) == RoleEnum.TRANSFORMER.name
    )
    assert community_to_role_name(CommunityEnum.ACADEMICS) == RoleEnum.ACADEMIC.name


def test_community_to_role_name_with_string():
    """Test converting community string to role name."""
    assert community_to_role_name("PRESS_MEDIA") == RoleEnum.PRESS_MEDIA.name
    assert community_to_role_name("COMMUNICANTS") == RoleEnum.PRESS_RELATIONS.name
    assert community_to_role_name("LEADERS_EXPERTS") == RoleEnum.EXPERT.name
    assert community_to_role_name("TRANSFORMERS") == RoleEnum.TRANSFORMER.name
    assert community_to_role_name("ACADEMICS") == RoleEnum.ACADEMIC.name


def test_community_to_role_enum():
    """Test getting Role object from community."""
    # Create role map
    role_press = Role(name=RoleEnum.PRESS_MEDIA.name)
    role_pr = Role(name=RoleEnum.PRESS_RELATIONS.name)
    role_expert = Role(name=RoleEnum.EXPERT.name)
    role_transformer = Role(name=RoleEnum.TRANSFORMER.name)
    role_academic = Role(name=RoleEnum.ACADEMIC.name)

    role_map = {
        RoleEnum.PRESS_MEDIA.name: role_press,
        RoleEnum.PRESS_RELATIONS.name: role_pr,
        RoleEnum.EXPERT.name: role_expert,
        RoleEnum.TRANSFORMER.name: role_transformer,
        RoleEnum.ACADEMIC.name: role_academic,
    }

    # Test with enum
    result = community_to_role_enum(role_map, CommunityEnum.PRESS_MEDIA)
    assert result == role_press

    # Test with string
    result = community_to_role_enum(role_map, "COMMUNICANTS")
    assert result == role_pr


def test_set_user_role_from_community_initial_assignment():
    """First assignment lands a single community role on the user."""
    user = User(email="test@example.com")
    role_map = _full_role_map()

    assert len(user.roles) == 0

    set_user_role_from_community(role_map, user, CommunityEnum.PRESS_MEDIA)
    assert [r.name for r in user.roles] == [RoleEnum.PRESS_MEDIA.name]


def test_set_user_role_from_community_replaces_previous():
    """Changing community must REMOVE the previous community role.

    Regression test for the RP-sees-Newsroom bug: a user who started as
    PRESS_MEDIA and updated their KYC profile to COMMUNICANTS used to
    keep both roles, silently granting them Newsroom access. The single-
    community invariant is now enforced here.
    """
    user = User(email="test@example.com")
    role_map = _full_role_map()

    set_user_role_from_community(role_map, user, CommunityEnum.PRESS_MEDIA)
    set_user_role_from_community(role_map, user, "COMMUNICANTS")

    role_names = {r.name for r in user.roles}
    assert role_names == {RoleEnum.PRESS_RELATIONS.name}
    assert RoleEnum.PRESS_MEDIA.name not in role_names


def test_set_user_role_from_community_leaves_non_community_roles_untouched():
    """Orthogonal roles (MANAGER, ADMIN, ...) must not be touched."""
    user = User(email="test@example.com")
    role_map = _full_role_map()

    user.roles.append(role_map[RoleEnum.MANAGER.name])
    set_user_role_from_community(role_map, user, CommunityEnum.PRESS_MEDIA)
    set_user_role_from_community(role_map, user, CommunityEnum.LEADERS_EXPERTS)

    role_names = {r.name for r in user.roles}
    assert role_names == {RoleEnum.MANAGER.name, RoleEnum.EXPERT.name}


def test_append_user_role_from_community_is_alias_for_set():
    """Legacy import still works and carries the new (correct) semantics."""
    assert append_user_role_from_community is set_user_role_from_community


def test_set_user_role_from_community_idempotent():
    """Re-applying the same community doesn't duplicate the role."""
    user = User(email="test@example.com")
    role_map = _full_role_map()

    set_user_role_from_community(role_map, user, CommunityEnum.PRESS_MEDIA)
    set_user_role_from_community(role_map, user, CommunityEnum.PRESS_MEDIA)

    assert [r.name for r in user.roles] == [RoleEnum.PRESS_MEDIA.name]
