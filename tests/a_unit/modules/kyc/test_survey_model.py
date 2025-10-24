# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Tests for KYC survey model."""

from __future__ import annotations

import pytest

from app.modules.kyc.survey_model import (
    get_survey_fields,
    get_survey_model,
    get_survey_profile,
    get_survey_profile_ids,
    load_survey_model,
)


def test_load_survey_model():
    """Test load_survey_model function."""
    result = load_survey_model()

    # Should return a dictionary with expected keys
    assert isinstance(result, dict)
    assert "communities" in result
    assert "survey_fields" in result
    assert "profiles" in result


def test_get_survey_model():
    """Test get_survey_model function."""
    result = get_survey_model()

    # Should return the same structure as load_survey_model
    assert isinstance(result, dict)
    assert "communities" in result
    assert "survey_fields" in result
    assert "profiles" in result


def test_get_survey_profile_ids():
    """Test get_survey_profile_ids function."""
    result = get_survey_profile_ids()

    # Should return a list of profile IDs
    assert isinstance(result, list)
    assert len(result) > 0
    # All items should be strings
    assert all(isinstance(pid, str) for pid in result)


def test_get_survey_profile():
    """Test get_survey_profile function."""
    # Get a valid profile ID first
    profile_ids = get_survey_profile_ids()
    assert len(profile_ids) > 0

    # Get a profile by valid ID
    profile = get_survey_profile(profile_ids[0])
    assert profile is not None
    assert profile.id == profile_ids[0]


def test_get_survey_profile_invalid_id():
    """Test get_survey_profile with invalid profile ID."""
    with pytest.raises(ValueError, match="Unknown profile"):
        get_survey_profile("INVALID_PROFILE_ID_THAT_DOES_NOT_EXIST")


def test_get_survey_fields():
    """Test get_survey_fields function."""
    result = get_survey_fields()

    # Should return a list of SurveyField objects
    assert isinstance(result, list)
    # Should have at least some fields
    assert len(result) > 0
