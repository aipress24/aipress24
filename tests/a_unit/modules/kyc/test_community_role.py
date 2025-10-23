# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

import pytest

from app.enums import CommunityEnum, RoleEnum
from app.models.auth import Role, User
from app.modules.kyc.community_role import (
    append_user_role_from_community,
    community_to_role_enum,
    community_to_role_name,
)


def test_community_to_role_name_with_enum():
    """Test converting CommunityEnum to role name."""
    assert (
        community_to_role_name(CommunityEnum.PRESS_MEDIA)
        == RoleEnum.PRESS_MEDIA.name
    )
    assert (
        community_to_role_name(CommunityEnum.COMMUNICANTS)
        == RoleEnum.PRESS_RELATIONS.name
    )
    assert (
        community_to_role_name(CommunityEnum.LEADERS_EXPERTS)
        == RoleEnum.EXPERT.name
    )
    assert (
        community_to_role_name(CommunityEnum.TRANSFORMERS)
        == RoleEnum.TRANSFORMER.name
    )
    assert (
        community_to_role_name(CommunityEnum.ACADEMICS) == RoleEnum.ACADEMIC.name
    )


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


def test_append_user_role_from_community():
    """Test appending role to user from community."""
    user = User(email="test@example.com")

    # Create role map
    role_press = Role(name=RoleEnum.PRESS_MEDIA.name)
    role_map = {RoleEnum.PRESS_MEDIA.name: role_press}

    # Initially user has no roles
    assert len(user.roles) == 0

    # Append role using enum
    append_user_role_from_community(role_map, user, CommunityEnum.PRESS_MEDIA)
    assert len(user.roles) == 1
    assert user.roles[0] == role_press

    # Append role using string
    role_expert = Role(name=RoleEnum.EXPERT.name)
    role_map[RoleEnum.EXPERT.name] = role_expert
    append_user_role_from_community(role_map, user, "LEADERS_EXPERTS")
    assert len(user.roles) == 2
    assert role_expert in user.roles
