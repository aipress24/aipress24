# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Tests for KYC survey dataclass."""

from __future__ import annotations

from app.enums import CommunityEnum, ContactTypeEnum, ProfileEnum
from app.modules.kyc.survey_dataclass import (
    Group,
    SurveyCommunities,
    SurveyCommunity,
    SurveyField,
    SurveyProfile,
)


def test_survey_profile_str():
    """Test SurveyProfile __str__ method."""
    profile = SurveyProfile(
        id="test_profile",
        description="Test Profile Description",
        code=ProfileEnum.PM_JR_ME,
        community=CommunityEnum.PRESS_MEDIA,
    )

    result = str(profile)
    assert "test_profile" in result
    assert "PM_JR_ME" in result or "PRESS_MEDIA" in result
    assert "Test Profile Description" in result


def test_survey_profile_label():
    """Test SurveyProfile label property."""
    profile = SurveyProfile(description="My Profile Label")
    assert profile.label == "My Profile Label"


def test_survey_profile_organisation_field():
    """Test SurveyProfile organisation_field property."""
    # Create fields
    field1 = SurveyField(name="email", is_organisation=False)
    field2 = SurveyField(name="org_name", is_organisation=True)
    field3 = SurveyField(name="phone", is_organisation=False)

    # Create groups
    group1 = Group(label="Group 1", survey_fields=[(field1, "M")])
    group2 = Group(label="Group 2", survey_fields=[(field2, "M"), (field3, "O")])

    # Create profile
    profile = SurveyProfile(
        id="test",
        groups=[group1, group2],
    )

    # Should find and cache the organisation field
    assert profile.organisation_field == "org_name"

    # Test caching - should return same value
    assert profile.organisation_field == "org_name"


def test_survey_profile_fields_all():
    """Test SurveyProfile fields iterator without filtering."""
    field1 = SurveyField(name="field1")
    field2 = SurveyField(name="field2")
    field3 = SurveyField(name="field3")

    group = Group(
        label="Test Group",
        survey_fields=[
            (field1, "M"),  # Mandatory
            (field2, "O"),  # Optional
            (field3, "M"),  # Mandatory
        ],
    )

    profile = SurveyProfile(groups=[group])

    # Get all fields
    fields = list(profile.fields(only_mandatory=False))
    assert len(fields) == 3
    assert field1 in fields
    assert field2 in fields
    assert field3 in fields


def test_survey_profile_fields_mandatory_only():
    """Test SurveyProfile fields iterator with mandatory filtering."""
    field1 = SurveyField(name="field1")
    field2 = SurveyField(name="field2")
    field3 = SurveyField(name="field3")

    group = Group(
        label="Test Group",
        survey_fields=[
            (field1, "M"),  # Mandatory
            (field2, "O"),  # Optional
            (field3, "M"),  # Mandatory
        ],
    )

    profile = SurveyProfile(groups=[group])

    # Get only mandatory fields
    fields = list(profile.fields(only_mandatory=True))
    assert len(fields) == 2
    assert field1 in fields
    assert field3 in fields
    assert field2 not in fields


def test_survey_field_is_visible():
    """Test SurveyField is_visible method."""
    field = SurveyField(
        name="test",
        public_mini=True,
        public_default=True,
        public_maxi=True,
    )

    # Level 0 (minimal) checks public_mini
    assert field.is_visible(0) is True

    # Level 1 (default) checks public_default
    assert field.is_visible(1) is True

    # Level 2+ (maxi) checks public_maxi
    assert field.is_visible(2) is True
    assert field.is_visible(3) is True

    # Test with selective visibility
    field_selective = SurveyField(
        name="selective",
        public_mini=False,
        public_default=True,
        public_maxi=True,
    )

    assert field_selective.is_visible(0) is False
    assert field_selective.is_visible(1) is True
    assert field_selective.is_visible(2) is True


def test_survey_field_str():
    """Test SurveyField __str__ method."""
    field = SurveyField(
        id="field_id",
        name="field_name",
        type="text",
        description="This is a test field description that is longer than 20 chars",
    )

    result = str(field)
    assert "field_id" in result
    assert "field_name" in result
    assert "text" in result
    # Description should be truncated to 20 chars
    assert len(result.split("This is a test field")[1].split(",")[0]) <= 20


def test_survey_communities_add_profile():
    """Test SurveyCommunities add_profile method."""
    communities = SurveyCommunities()

    profile1 = SurveyProfile(
        id="profile1",
        community=CommunityEnum.PRESS_MEDIA,
    )

    # Add first profile
    communities.add_profile(profile1)
    assert len(list(communities)) == 1

    # Add second profile to same community
    profile2 = SurveyProfile(
        id="profile2",
        community=CommunityEnum.PRESS_MEDIA,
    )
    communities.add_profile(profile2)
    assert len(list(communities)) == 1

    # Check profiles are in the community
    community = communities.get("PRESS_MEDIA")
    assert community is not None
    assert len(community.profiles) == 2

    # Add profile to different community
    profile3 = SurveyProfile(
        id="profile3",
        community=CommunityEnum.COMMUNICANTS,
    )
    communities.add_profile(profile3)
    assert len(list(communities)) == 2


def test_survey_communities_get():
    """Test SurveyCommunities get method."""
    communities = SurveyCommunities()

    profile = SurveyProfile(
        id="profile1",
        community=CommunityEnum.ACADEMICS,
    )
    communities.add_profile(profile)

    # Get existing community
    community = communities.get("ACADEMICS")
    assert community is not None
    assert community.id == "ACADEMICS"

    # Get non-existing community
    assert communities.get("NONEXISTENT") is None


def test_survey_communities_iter():
    """Test SurveyCommunities __iter__ method."""
    communities = SurveyCommunities()

    profile1 = SurveyProfile(id="p1", community=CommunityEnum.PRESS_MEDIA)
    profile2 = SurveyProfile(id="p2", community=CommunityEnum.COMMUNICANTS)
    profile3 = SurveyProfile(id="p3", community=CommunityEnum.ACADEMICS)

    communities.add_profile(profile1)
    communities.add_profile(profile2)
    communities.add_profile(profile3)

    # Iterate over communities
    community_list = list(communities)
    assert len(community_list) == 3

    # Check all are SurveyCommunity instances
    for community in community_list:
        assert isinstance(community, SurveyCommunity)
