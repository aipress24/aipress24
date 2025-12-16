# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Unit tests for admin/pages/show_org.py - OrgVM class."""

from __future__ import annotations

from dataclasses import dataclass, field
from unittest.mock import Mock

from app.modules.admin.pages.show_org import OrgVM


@dataclass
class StubOrganisation:
    """Stub organisation for testing OrgVM logic."""

    is_auto: bool = False
    screenshot_id: str | None = None
    formatted_address: str = ""
    members: list = field(default_factory=list)
    managers: list = field(default_factory=list)
    leaders: list = field(default_factory=list)
    id: int = 1

    def logo_image_signed_url(self) -> str:
        return "https://s3.example.com/logo.png"


class TestOrgVMGetLogoUrl:
    """Test OrgVM.get_logo_url() logic."""

    def test_auto_org_returns_static_logo(self):
        """Test is_auto=True returns static placeholder logo."""
        org = StubOrganisation(is_auto=True)
        vm = OrgVM(org)

        result = vm.get_logo_url()

        assert result == "/static/img/logo-page-non-officielle.png"

    def test_non_auto_org_returns_signed_url(self):
        """Test is_auto=False returns S3 signed URL."""
        org = StubOrganisation(is_auto=False)
        vm = OrgVM(org)

        result = vm.get_logo_url()

        assert result == "https://s3.example.com/logo.png"


class TestOrgVMGetScreenshotUrl:
    """Test OrgVM.get_screenshot_url() logic."""

    def test_no_screenshot_returns_empty(self, app):
        """Test no screenshot_id returns empty string."""
        org = StubOrganisation(screenshot_id=None)
        vm = OrgVM(org)

        result = vm.get_screenshot_url()

        assert result == ""

    def test_empty_screenshot_returns_empty(self, app):
        """Test empty screenshot_id returns empty string."""
        org = StubOrganisation(screenshot_id="")
        vm = OrgVM(org)

        result = vm.get_screenshot_url()

        assert result == ""

    def test_with_screenshot_returns_url(self, app):
        """Test screenshot_id builds URL from config."""
        app.config["S3_PUBLIC_URL"] = "https://s3.example.com"
        org = StubOrganisation(screenshot_id="abc123")
        vm = OrgVM(org)

        result = vm.get_screenshot_url()

        assert result == "https://s3.example.com/abc123"


class TestOrgVMExtraAttrs:
    """Test OrgVM.extra_attrs() method."""

    def test_extra_attrs_returns_expected_keys(self, app):
        """Test extra_attrs returns dict with required keys."""
        org = StubOrganisation(
            members=[Mock(name="user1"), Mock(name="user2")],
            managers=[Mock(name="manager1")],
            leaders=[Mock(name="leader1")],
            formatted_address="123 Main St",
        )
        vm = OrgVM(org)

        # Mock invitations function since it requires DB
        import app.modules.admin.pages.show_org as show_org_module

        original_fn = show_org_module.emails_invited_to_organisation
        show_org_module.emails_invited_to_organisation = lambda org_id: ["a@b.com"]

        try:
            result = vm.extra_attrs()
        finally:
            show_org_module.emails_invited_to_organisation = original_fn

        assert "members" in result
        assert "count_members" in result
        assert "managers" in result
        assert "leaders" in result
        assert "invitations_emails" in result
        assert "logo_url" in result
        assert "screenshot_url" in result
        assert "address_formatted" in result

    def test_extra_attrs_count_members(self, app):
        """Test extra_attrs correctly counts members."""
        members = [Mock(), Mock(), Mock()]
        org = StubOrganisation(members=members)
        vm = OrgVM(org)

        import app.modules.admin.pages.show_org as show_org_module

        original_fn = show_org_module.emails_invited_to_organisation
        show_org_module.emails_invited_to_organisation = lambda org_id: []

        try:
            result = vm.extra_attrs()
        finally:
            show_org_module.emails_invited_to_organisation = original_fn

        assert result["count_members"] == 3


class TestOrgVMGetMembers:
    """Test OrgVM.get_members() method."""

    def test_get_members_returns_list(self):
        """Test get_members converts members to list."""
        members = [Mock(), Mock()]
        org = StubOrganisation(members=members)
        vm = OrgVM(org)

        result = vm.get_members()

        assert isinstance(result, list)
        assert len(result) == 2
