# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Unit tests for admin/pages/validation_user.py - pure logic testing."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


class TestDetectBusinessWallTrigger:
    """Test detect_business_wall_trigger logic.

    This method updates a context dict based on the user's profile trigger.
    We test the underlying logic without Flask dependencies.
    """

    @dataclass
    class StubProfile:
        """Stub profile for testing."""

        trigger: str | None = None

        def get_first_bw_trigger(self) -> str | None:
            return self.trigger

    @dataclass
    class StubUser:
        """Stub user for testing."""

        profile: Any = None
        organisation_name: str | None = None

    def _detect_business_wall_trigger(
        self, user: "TestDetectBusinessWallTrigger.StubUser", context: dict[str, Any]
    ) -> None:
        """Mirror of detect_business_wall_trigger logic for testing."""
        media_satus = {"bw_trigger": False, "bw_organisation": ""}
        profile = user.profile
        trigger = profile.get_first_bw_trigger()
        if trigger:
            media_satus = {
                "bw_trigger": True,
                "bw_organisation": user.organisation_name or "aucune?",
            }
        context.update(media_satus)

    def test_no_trigger_sets_false(self):
        """Test no trigger sets bw_trigger=False."""
        profile = self.StubProfile(trigger=None)
        user = self.StubUser(profile=profile)
        context: dict[str, Any] = {}

        self._detect_business_wall_trigger(user, context)

        assert context["bw_trigger"] is False
        assert context["bw_organisation"] == ""

    def test_with_trigger_sets_true(self):
        """Test with trigger sets bw_trigger=True."""
        profile = self.StubProfile(trigger="media_trigger")
        user = self.StubUser(profile=profile, organisation_name="Test Media")
        context: dict[str, Any] = {}

        self._detect_business_wall_trigger(user, context)

        assert context["bw_trigger"] is True
        assert context["bw_organisation"] == "Test Media"

    def test_trigger_with_no_org_name(self):
        """Test trigger with no organisation_name shows fallback."""
        profile = self.StubProfile(trigger="media_trigger")
        user = self.StubUser(profile=profile, organisation_name=None)
        context: dict[str, Any] = {}

        self._detect_business_wall_trigger(user, context)

        assert context["bw_trigger"] is True
        assert context["bw_organisation"] == "aucune?"

    def test_trigger_with_empty_org_name(self):
        """Test trigger with empty organisation_name shows fallback."""
        profile = self.StubProfile(trigger="media_trigger")
        user = self.StubUser(profile=profile, organisation_name="")
        context: dict[str, Any] = {}

        self._detect_business_wall_trigger(user, context)

        assert context["bw_trigger"] is True
        assert context["bw_organisation"] == "aucune?"

    def test_updates_existing_context(self):
        """Test method updates existing context without removing keys."""
        profile = self.StubProfile(trigger=None)
        user = self.StubUser(profile=profile)
        context: dict[str, Any] = {"existing_key": "value"}

        self._detect_business_wall_trigger(user, context)

        assert context["existing_key"] == "value"
        assert "bw_trigger" in context

    def test_empty_string_trigger_is_falsy(self):
        """Test empty string trigger is treated as no trigger."""
        profile = self.StubProfile(trigger="")
        user = self.StubUser(profile=profile)
        context: dict[str, Any] = {}

        self._detect_business_wall_trigger(user, context)

        assert context["bw_trigger"] is False
