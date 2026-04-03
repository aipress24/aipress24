# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Unit tests for kyc/organisation_utils.py

These tests use real database operations with proper survey profile IDs
to control the organisation_field_name_origin property value.

Survey Profile ID to organisation_field mapping:
- P001-P005, P008: nom_media
- P006-P007: nom_media_instit
- P009-P011: nom_agence_rp
- P012-P029: nom_orga
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

import pytest

from app.models.auth import KYCProfile, User
from app.models.invitation import Invitation
from app.models.organisation import Organisation
from app.modules.kyc.organisation_utils import (
    _find_kyc_organisation_name,
    find_inviting_organisations,
    get_organisation_family,
    get_organisation_for_noms_com,
    get_organisation_for_noms_medias,
    get_organisation_for_noms_orgas,
    retrieve_user_organisation,
    store_auto_organisation,
)

if TYPE_CHECKING:
    from flask_sqlalchemy import SQLAlchemy

# Profile IDs mapped to their organisation_field values
PROFILE_ID_NOM_MEDIA = "P001"  # organisation_field = "nom_media"
PROFILE_ID_NOM_ORGA = "P012"  # organisation_field = "nom_orga"


@pytest.mark.skip(reason="There is no more Organisation type")
class TestGetOrganisationFamily:
    """Test suite for get_organisation_family function."""

    def test_returns_list_of_auto_orgs(self, db: SQLAlchemy) -> None:
        """Test getting organisations of AUTO family."""
        org1 = Organisation(name="Auto Org 1")
        org2 = Organisation(name="Auto Org 2")

        org3 = Organisation(name="Media Org", bw_active="media", bw_id=uuid4())
        db.session.add_all([org1, org2, org3])
        db.session.flush()

        result = get_organisation_family(None)

        assert "Auto Org 1" in result
        assert "Auto Org 2" in result
        assert "Media Org" not in result

    def test_returns_list_of_media_orgs(self, db: SQLAlchemy) -> None:
        """Test getting organisations of MEDIA family."""
        org1 = Organisation(name="Media Org 1", bw_active="media", bw_id=uuid4())
        org2 = Organisation(name="Media Org 2", bw_active="media", bw_id=uuid4())
        org3 = Organisation(name="Auto Org")
        db.session.add_all([org1, org2, org3])
        db.session.flush()

        result = get_organisation_family("media")

        assert "Media Org 1" in result
        assert "Media Org 2" in result
        assert "Auto Org" not in result

    def test_returns_sorted_list(self, db: SQLAlchemy) -> None:
        """Test that results are sorted by name."""
        org1 = Organisation(name="Zebra Corp", bw_active="pr", bw_id=uuid4())
        org2 = Organisation(name="Alpha Inc", bw_active="pr", bw_id=uuid4())
        org3 = Organisation(name="Beta Ltd", bw_active="pr", bw_id=uuid4())
        db.session.add_all([org1, org2, org3])
        db.session.flush()

        result = get_organisation_family("pr")

        assert result.index("Alpha Inc") < result.index("Beta Ltd")
        assert result.index("Beta Ltd") < result.index("Zebra Corp")

    def test_excludes_other_types(self, db: SQLAlchemy) -> None:
        """Test excludes organisations of different types."""
        # Create orgs of different types, none with AGENCY type
        org1 = Organisation(name="Exclude Test Media", bw_active="media", bw_id=uuid4())
        org2 = Organisation(name="Exclude Test COM", bw_active="pr", bw_id=uuid4())
        db.session.add_all([org1, org2])
        db.session.flush()

        result = get_organisation_family("transformers")

        # Should not include the MEDIA or COM orgs we just created
        assert "Exclude Test Media" not in result
        assert "Exclude Test COM" not in result


class TestGetOrganisationForNoms:
    """Test suite for get_organisation_for_noms_* functions."""

    def test_get_noms_medias_returns_media_agency_auto(self, db: SQLAlchemy) -> None:
        """Test get_organisation_for_noms_medias returns MEDIA, AUTO orgs (no more AGENCY)."""
        org_media = Organisation(name="Media Org", bw_active="media", bw_id=uuid4())
        org_agency = Organisation(name="Agency Org", bw_active="media", bw_id=uuid4())
        org_auto = Organisation(name="Auto Org")
        org_com = Organisation(name="Com Org", bw_active="pr", bw_id=uuid4())
        db.session.add_all([org_media, org_agency, org_auto, org_com])
        db.session.flush()

        result = get_organisation_for_noms_medias()

        assert "Media Org" in result
        assert "Agency Org" in result
        assert "Auto Org" in result
        assert "Com Org" not in result

    def test_get_noms_orgas_returns_other_auto(self, db: SQLAlchemy) -> None:
        """Test get_organisation_for_noms_orgas returns OTHER, AUTO orgs."""
        org_other = Organisation(name="Other Org", bw_active="academics", bw_id=uuid4())
        org_auto = Organisation(name="Auto Org 2")
        org_media = Organisation(name="Media Org 2", bw_active="media", bw_id=uuid4())
        db.session.add_all([org_other, org_auto, org_media])
        db.session.flush()

        result = get_organisation_for_noms_orgas()

        assert "Other Org" in result
        assert "Auto Org 2" in result
        assert "Media Org 2" not in result

    def test_get_noms_com_returns_com_auto(self, db: SQLAlchemy) -> None:
        """Test get_organisation_for_noms_com returns COM, AUTO orgs."""
        org_com = Organisation(name="Com Org 2", bw_active="pr", bw_id=uuid4())
        org_auto = Organisation(name="Auto Org 3")
        org_media = Organisation(name="Media Org 3", bw_active="media", bw_id=uuid4())
        db.session.add_all([org_com, org_auto, org_media])
        db.session.flush()

        result = get_organisation_for_noms_com()

        assert "Com Org 2" in result
        assert "Auto Org 3" in result
        assert "Media Org 3" not in result


class TestFindKycOrganisationName:
    """Test suite for _find_kyc_organisation_name function.

    Uses real survey profile IDs to control the organisation_field_name_origin
    property value. P001 maps to "nom_media" field.
    """

    def test_returns_string_value(self, db: SQLAlchemy) -> None:
        """Test returns organisation name from string field."""
        user = User(email="test_kyc_str@example.com")
        profile = KYCProfile()
        profile.profile_id = PROFILE_ID_NOM_MEDIA  # Maps to "nom_media"
        profile.info_professionnelle = {"nom_media": "Test Media Corp"}
        user.profile = profile
        db.session.add_all([user, profile])
        db.session.flush()

        result = _find_kyc_organisation_name(user)

        assert result == "Test Media Corp"

    def test_returns_empty_for_empty_value(self, db: SQLAlchemy) -> None:
        """Test returns empty string when field value is empty."""
        user = User(email="test_kyc_empty@example.com")
        profile = KYCProfile()
        profile.profile_id = PROFILE_ID_NOM_MEDIA
        profile.info_professionnelle = {"nom_media": ""}
        user.profile = profile
        db.session.add_all([user, profile])
        db.session.flush()

        result = _find_kyc_organisation_name(user)

        assert result == ""

    def test_returns_empty_for_none_value(self, db: SQLAlchemy) -> None:
        """Test returns empty string when field value is None."""
        user = User(email="test_kyc_none@example.com")
        profile = KYCProfile()
        profile.profile_id = PROFILE_ID_NOM_MEDIA
        profile.info_professionnelle = {"nom_media": None}
        user.profile = profile
        db.session.add_all([user, profile])
        db.session.flush()

        result = _find_kyc_organisation_name(user)

        assert result == ""

    def test_strips_whitespace(self, db: SQLAlchemy) -> None:
        """Test strips whitespace from organisation name."""
        user = User(email="test_kyc_whitespace@example.com")
        profile = KYCProfile()
        profile.profile_id = PROFILE_ID_NOM_MEDIA
        profile.info_professionnelle = {"nom_media": "  Padded Name  "}
        user.profile = profile
        db.session.add_all([user, profile])
        db.session.flush()

        result = _find_kyc_organisation_name(user)

        assert result == "Padded Name"

    def test_handles_missing_field(self, db: SQLAlchemy) -> None:
        """Test handles case where field is not in info_professionnelle."""
        user = User(email="test_kyc_missing@example.com")
        profile = KYCProfile()
        profile.profile_id = PROFILE_ID_NOM_MEDIA
        profile.info_professionnelle = {}  # No nom_media field
        user.profile = profile
        db.session.add_all([user, profile])
        db.session.flush()

        result = _find_kyc_organisation_name(user)

        assert result == ""


class TestFindInvitingOrganisations:
    """Test suite for find_inviting_organisations function."""

    def test_returns_orgs_with_invitations(self, db: SQLAlchemy) -> None:
        """Test returns organisations that have invited the email."""
        org1 = Organisation(name="Inviting Org 1", bw_active="media", bw_id=uuid4())
        org2 = Organisation(name="Inviting Org 2", bw_active="pr", bw_id=uuid4())
        db.session.add_all([org1, org2])
        db.session.flush()

        inv1 = Invitation(email="invited@example.com", organisation_id=org1.id)
        inv2 = Invitation(email="invited@example.com", organisation_id=org2.id)
        db.session.add_all([inv1, inv2])
        db.session.flush()

        result = find_inviting_organisations("invited@example.com")

        org_names = [org.name for org in result]
        assert "Inviting Org 1" in org_names
        assert "Inviting Org 2" in org_names

    def test_case_insensitive_email_matching(self, db: SQLAlchemy) -> None:
        """Test email matching is case insensitive."""
        org = Organisation(
            name="KYC Case Test Org Unique", bw_active="media", bw_id=uuid4()
        )
        db.session.add(org)
        db.session.flush()

        inv = Invitation(email="KycCaseUnique@Example.COM", organisation_id=org.id)
        db.session.add(inv)
        db.session.flush()

        result = find_inviting_organisations("kyccaseunique@example.com")

        assert len(result) == 1
        assert result[0].name == "KYC Case Test Org Unique"

    def test_returns_empty_for_no_invitations(self, db: SQLAlchemy) -> None:
        """Test returns empty list when no invitations exist."""
        result = find_inviting_organisations("noinvite@example.com")
        assert result == []

    def test_returns_empty_for_empty_email(self, db: SQLAlchemy) -> None:
        """Test returns empty list for empty email."""
        result = find_inviting_organisations("")
        assert result == []

    def test_returns_empty_for_invalid_email(self, db: SQLAlchemy) -> None:
        """Test returns empty list for email without @."""
        result = find_inviting_organisations("invalid-email")
        assert result == []


class TestStoreAutoOrganisation:
    """Test suite for store_auto_organisation function."""

    def test_creates_new_auto_org(self, db: SQLAlchemy) -> None:
        """Test creates new AUTO organisation when it doesn't exist."""
        user = User(email="store_auto_new@example.com")
        profile = KYCProfile()
        user.profile = profile
        db.session.add_all([user, profile])
        db.session.flush()

        result = store_auto_organisation(user, org_name="New Auto Org")

        assert result is not None
        assert result.name == "New Auto Org"
        assert result.is_auto is True

    def test_returns_existing_auto_org(self, db: SQLAlchemy) -> None:
        """Test returns existing AUTO org instead of creating duplicate."""
        existing_org = Organisation(name="Existing Auto")
        db.session.add(existing_org)
        db.session.flush()

        user = User(email="store_auto_existing@example.com")
        profile = KYCProfile()
        user.profile = profile
        db.session.add_all([user, profile])
        db.session.flush()

        result = store_auto_organisation(user, org_name="Existing Auto")

        assert result is not None
        assert result.id == existing_org.id

    def test_returns_none_for_empty_name(self, db: SQLAlchemy) -> None:
        """Test returns None when organisation name is empty."""
        user = User(email="store_auto_empty@example.com")
        profile = KYCProfile()
        user.profile = profile
        db.session.add_all([user, profile])
        db.session.flush()

        result = store_auto_organisation(user, org_name="")

        assert result is None

    def test_returns_none_for_whitespace_name(self, db: SQLAlchemy) -> None:
        """Test returns None when organisation name is whitespace only."""
        user = User(email="store_auto_whitespace@example.com")
        profile = KYCProfile()
        user.profile = profile
        db.session.add_all([user, profile])
        db.session.flush()

        result = store_auto_organisation(user, org_name="   ")

        assert result is None

    def test_strips_whitespace_from_name(self, db: SQLAlchemy) -> None:
        """Test strips whitespace from organisation name."""
        user = User(email="store_auto_strip@example.com")
        profile = KYCProfile()
        user.profile = profile
        db.session.add_all([user, profile])
        db.session.flush()

        result = store_auto_organisation(user, org_name="  Stripped Org  ")

        assert result is not None
        assert result.name == "Stripped Org"

    def test_creates_auto_org_even_if_non_auto_exists(self, db: SQLAlchemy) -> None:
        """Test creates AUTO org even if non-AUTO org with same name exists."""
        media_org = Organisation(name="Dual Name Org", bw_active="media", bw_id=uuid4())
        db.session.add(media_org)
        db.session.flush()

        user = User(email="store_auto_dual@example.com")
        profile = KYCProfile()
        user.profile = profile
        db.session.add_all([user, profile])
        db.session.flush()

        result = store_auto_organisation(user, org_name="Dual Name Org")

        assert result is not None
        assert result.is_auto
        assert result.id != media_org.id


class TestRetrieveUserOrganisation:
    """Test suite for retrieve_user_organisation function.

    Uses real survey profile IDs to control the organisation_field_name_origin
    property value.
    """

    def test_returns_inviting_org_when_name_matches(self, db: SQLAlchemy) -> None:
        """Test returns inviting organisation when name matches."""
        org = Organisation(name="Matching Org", bw_active="media", bw_id=uuid4())
        db.session.add(org)
        db.session.flush()

        user = User(email="retrieve_match@example.com")
        profile = KYCProfile()
        profile.profile_id = PROFILE_ID_NOM_MEDIA
        profile.info_professionnelle = {"nom_media": "Matching Org"}
        user.profile = profile
        db.session.add_all([user, profile])
        db.session.flush()

        inv = Invitation(email="retrieve_match@example.com", organisation_id=org.id)
        db.session.add(inv)
        db.session.flush()

        result = retrieve_user_organisation(user)

        assert result is not None
        assert result.id == org.id
        assert result.name == "Matching Org"

    def test_returns_none_when_no_org_name(self, db: SQLAlchemy) -> None:
        """Test returns None when user has no organisation name."""
        user = User(email="retrieve_none@example.com")
        profile = KYCProfile()
        profile.profile_id = PROFILE_ID_NOM_MEDIA
        profile.info_professionnelle = {"nom_media": ""}
        user.profile = profile
        db.session.add_all([user, profile])
        db.session.flush()

        result = retrieve_user_organisation(user)

        assert result is None

    @pytest.mark.skip(reason="FIXME: There is no more Organisation type / AUTO")
    def test_creates_auto_org_when_no_invitation_match(self, db: SQLAlchemy) -> None:
        """Test creates AUTO org when no inviting org matches."""
        user = User(email="retrieve_auto@example.com")
        profile = KYCProfile()
        profile.profile_id = PROFILE_ID_NOM_MEDIA
        profile.info_professionnelle = {"nom_media": "Non Invited Org"}
        user.profile = profile
        db.session.add_all([user, profile])
        db.session.flush()

        result = retrieve_user_organisation(user)

        assert result is not None
        assert result.name == "Non Invited Org"
        assert result.is_auto
