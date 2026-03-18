# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Integration tests for admin show_org views."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from app.models.auth import User
from app.models.organisation import Organisation
from app.modules.admin.views.show_org import OrgVM

if TYPE_CHECKING:
    from flask import Flask
    from sqlalchemy.orm import Session


@pytest.fixture
def organisation(db_session: Session) -> Organisation:
    """Create a test organisation."""
    org = Organisation(
        name="Test Organisation",
        address="123 Test Street",
        zip_code="75001",
        city="Paris",
        country="France",
    )
    db_session.add(org)
    db_session.flush()
    return org


@pytest.fixture
def auto_organisation(db_session: Session) -> Organisation:
    """Create an auto-generated organisation (inactive/AUTO)."""
    org = Organisation(
        name="Auto Organisation",
        active=False,
    )
    db_session.add(org)
    db_session.flush()
    return org


@pytest.fixture
def org_with_members(db_session: Session, organisation: Organisation) -> Organisation:
    """Create an organisation with members."""
    user1 = User(
        email="member1@example.com",
        first_name="Member",
        last_name="One",
        organisation_id=organisation.id,
    )
    user2 = User(
        email="member2@example.com",
        first_name="Member",
        last_name="Two",
        organisation_id=organisation.id,
    )
    db_session.add_all([user1, user2])
    db_session.flush()
    return organisation


class TestOrgVM:
    """Tests for OrgVM view model."""

    def test_org_property_returns_organisation(
        self, app: Flask, db_session: Session, organisation: Organisation
    ):
        """Test org property returns the wrapped organisation."""
        with app.test_request_context():
            vm = OrgVM(organisation)
            assert vm.org == organisation
            assert vm.org.name == "Test Organisation"

    def test_get_members_returns_list(
        self, app: Flask, db_session: Session, org_with_members: Organisation
    ):
        """Test get_members returns list of members."""
        with app.test_request_context():
            vm = OrgVM(org_with_members)
            members = vm.get_members()

            assert isinstance(members, list)
            assert len(members) == 2

    def test_get_logo_url_for_auto_org(
        self, app: Flask, db_session: Session, auto_organisation: Organisation
    ):
        """Test get_logo_url returns placeholder for auto orgs."""
        with app.test_request_context():
            vm = OrgVM(auto_organisation)
            url = vm.get_logo_url()

            assert url == "/static/img/logo-page-non-officielle.png"

    def test_get_logo_url_for_regular_org(
        self, app: Flask, db_session: Session, organisation: Organisation
    ):
        """Test get_logo_url returns signed URL for regular orgs."""
        with app.test_request_context():
            vm = OrgVM(organisation)
            url = vm.get_logo_url()

            # Should return a URL (possibly empty if no logo)
            assert isinstance(url, str)

    def test_get_screenshot_url_empty_when_no_screenshot(
        self, app: Flask, db_session: Session, organisation: Organisation
    ):
        """Test get_screenshot_url returns empty when no screenshot."""
        with app.test_request_context():
            vm = OrgVM(organisation)
            url = vm.get_screenshot_url()

            assert url == ""

    def test_extra_attrs_contains_expected_keys(
        self, app: Flask, db_session: Session, org_with_members: Organisation
    ):
        """Test extra_attrs returns dict with expected keys."""
        with app.test_request_context():
            vm = OrgVM(org_with_members)
            attrs = vm.extra_attrs()

            assert "members" in attrs
            assert "count_members" in attrs
            assert "invitations_emails" in attrs
            assert "logo_url" in attrs
            assert "screenshot_url" in attrs
            assert "address_formatted" in attrs

    def test_extra_attrs_count_members_matches_members_length(
        self, app: Flask, db_session: Session, org_with_members: Organisation
    ):
        """Test count_members matches actual member count."""
        with app.test_request_context():
            vm = OrgVM(org_with_members)
            attrs = vm.extra_attrs()

            assert attrs["count_members"] == len(attrs["members"])
            assert attrs["count_members"] == 2
