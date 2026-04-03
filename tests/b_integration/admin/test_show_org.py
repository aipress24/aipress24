# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Integration tests for admin show_org views."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from app.models.auth import KYCProfile, User
from app.models.organisation import Organisation
from app.modules.admin.org_email_utils import set_user_organisation
from app.modules.admin.views.show_org import OrgVM
from app.modules.bw.bw_activation.models import BusinessWall, BWStatus

if TYPE_CHECKING:
    from flask import Flask
    from sqlalchemy.orm import Session


@pytest.fixture
def organisation(db_session: Session) -> Organisation:
    """Create a test organisation with BW."""
    user = User(
        email=f"org_owner@example.com",
        first_name="John",
        last_name="Doe",
        active=True,
    )
    profile = KYCProfile()
    user.profile = profile
    db_session.add(user)
    db_session.flush()

    org = Organisation(
        name="Test Organisation",
    )
    db_session.add(org)
    db_session.flush()

    set_user_organisation(user, org)

    # Create BusinessWall with required fields
    bw = BusinessWall(
        organisation_id=org.id,
        bw_type="media",
        status=BWStatus.ACTIVE.value,
        owner_id=user.id,
        payer_id=user.id,
        name="bw different name",
        name_entity="bw entity name",
        # type_organisation
        # type_organisation_detail
        # siren
        # tva
        # agrement
        name_press="bw journal name",
        # type_presse_et_media
        # type_entreprise_media
        # type_agence_rp
        # clients
        # name_official
        # name_group
        # name_institution
        # positionnement_editorial
        # audience_cible
        # periodicite
        postal_address="123 rue Abc",
        pays_zip_ville="FRA",
        pays_zip_ville_detail="{FRA / 75001 Paris}",
    )

    bw.update_location_fields()

    db_session.add(bw)
    db_session.flush()

    # Link organisation to BW
    org.bw_id = bw.id
    org.bw_active = bw.bw_type

    db_session.flush()
    return org


@pytest.fixture
def auto_organisation(db_session: Session) -> Organisation:
    """Create an auto-generated organisation."""
    org = Organisation(name="Auto Organisation")
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
            assert len(members) == 3  # 2 + owner

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
            assert "address_formatted" in attrs

    def test_extra_attrs_count_members_matches_members_length(
        self, app: Flask, db_session: Session, org_with_members: Organisation
    ):
        """Test count_members matches actual member count."""
        with app.test_request_context():
            vm = OrgVM(org_with_members)
            attrs = vm.extra_attrs()

            assert attrs["count_members"] == len(attrs["members"])
            assert attrs["count_members"] == 3
