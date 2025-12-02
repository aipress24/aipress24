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

from flask_sqlalchemy import SQLAlchemy

from app.enums import BWTypeEnum, OrganisationTypeEnum, ProfileEnum
from app.models.auth import KYCProfile, User
from app.models.invitation import Invitation
from app.models.organisation import Organisation
from app.modules.kyc.organisation_utils import (
    _find_kyc_organisation_name,
    _set_activity_sectors,
    _set_media_types,
    _set_nom_groupe,
    _set_organization_types,
    find_inviting_organisations,
    get_organisation_choices_family,
    get_organisation_family,
    get_organisation_for_noms_com,
    get_organisation_for_noms_medias,
    get_organisation_for_noms_orgas,
    retrieve_user_organisation,
    specialize_organization_type,
    store_auto_organisation,
)


# Profile IDs mapped to their organisation_field values
PROFILE_ID_NOM_MEDIA = "P001"  # organisation_field = "nom_media"
PROFILE_ID_NOM_ORGA = "P012"  # organisation_field = "nom_orga"


class TestGetOrganisationFamily:
    """Test suite for get_organisation_family function."""

    def test_returns_list_of_auto_orgs(self, db: SQLAlchemy) -> None:
        """Test getting organisations of AUTO family."""
        org1 = Organisation(name="Auto Org 1", type=OrganisationTypeEnum.AUTO)
        org2 = Organisation(name="Auto Org 2", type=OrganisationTypeEnum.AUTO)
        org3 = Organisation(name="Media Org", type=OrganisationTypeEnum.MEDIA)
        db.session.add_all([org1, org2, org3])
        db.session.flush()

        result = get_organisation_family(OrganisationTypeEnum.AUTO)

        assert "Auto Org 1" in result
        assert "Auto Org 2" in result
        assert "Media Org" not in result

    def test_returns_list_of_media_orgs(self, db: SQLAlchemy) -> None:
        """Test getting organisations of MEDIA family."""
        org1 = Organisation(name="Media Org 1", type=OrganisationTypeEnum.MEDIA)
        org2 = Organisation(name="Media Org 2", type=OrganisationTypeEnum.MEDIA)
        org3 = Organisation(name="Auto Org", type=OrganisationTypeEnum.AUTO)
        db.session.add_all([org1, org2, org3])
        db.session.flush()

        result = get_organisation_family(OrganisationTypeEnum.MEDIA)

        assert "Media Org 1" in result
        assert "Media Org 2" in result
        assert "Auto Org" not in result

    def test_returns_sorted_list(self, db: SQLAlchemy) -> None:
        """Test that results are sorted by name."""
        org1 = Organisation(name="Zebra Corp", type=OrganisationTypeEnum.COM)
        org2 = Organisation(name="Alpha Inc", type=OrganisationTypeEnum.COM)
        org3 = Organisation(name="Beta Ltd", type=OrganisationTypeEnum.COM)
        db.session.add_all([org1, org2, org3])
        db.session.flush()

        result = get_organisation_family(OrganisationTypeEnum.COM)

        assert result.index("Alpha Inc") < result.index("Beta Ltd")
        assert result.index("Beta Ltd") < result.index("Zebra Corp")

    def test_excludes_other_types(self, db: SQLAlchemy) -> None:
        """Test excludes organisations of different types."""
        # Create orgs of different types, none with AGENCY type
        org1 = Organisation(name="Exclude Test Media", type=OrganisationTypeEnum.MEDIA)
        org2 = Organisation(name="Exclude Test COM", type=OrganisationTypeEnum.COM)
        db.session.add_all([org1, org2])
        db.session.flush()

        result = get_organisation_family(OrganisationTypeEnum.AGENCY)

        # Should not include the MEDIA or COM orgs we just created
        assert "Exclude Test Media" not in result
        assert "Exclude Test COM" not in result


class TestGetOrganisationForNoms:
    """Test suite for get_organisation_for_noms_* functions."""

    def test_get_noms_medias_returns_media_agency_auto(self, db: SQLAlchemy) -> None:
        """Test get_organisation_for_noms_medias returns MEDIA, AGENCY, AUTO orgs."""
        org_media = Organisation(name="Media Org", type=OrganisationTypeEnum.MEDIA)
        org_agency = Organisation(name="Agency Org", type=OrganisationTypeEnum.AGENCY)
        org_auto = Organisation(name="Auto Org", type=OrganisationTypeEnum.AUTO)
        org_com = Organisation(name="Com Org", type=OrganisationTypeEnum.COM)
        db.session.add_all([org_media, org_agency, org_auto, org_com])
        db.session.flush()

        result = get_organisation_for_noms_medias()

        assert "Media Org" in result
        assert "Agency Org" in result
        assert "Auto Org" in result
        assert "Com Org" not in result

    def test_get_noms_orgas_returns_other_auto(self, db: SQLAlchemy) -> None:
        """Test get_organisation_for_noms_orgas returns OTHER, AUTO orgs."""
        org_other = Organisation(name="Other Org", type=OrganisationTypeEnum.OTHER)
        org_auto = Organisation(name="Auto Org 2", type=OrganisationTypeEnum.AUTO)
        org_media = Organisation(name="Media Org 2", type=OrganisationTypeEnum.MEDIA)
        db.session.add_all([org_other, org_auto, org_media])
        db.session.flush()

        result = get_organisation_for_noms_orgas()

        assert "Other Org" in result
        assert "Auto Org 2" in result
        assert "Media Org 2" not in result

    def test_get_noms_com_returns_com_auto(self, db: SQLAlchemy) -> None:
        """Test get_organisation_for_noms_com returns COM, AUTO orgs."""
        org_com = Organisation(name="Com Org 2", type=OrganisationTypeEnum.COM)
        org_auto = Organisation(name="Auto Org 3", type=OrganisationTypeEnum.AUTO)
        org_media = Organisation(name="Media Org 3", type=OrganisationTypeEnum.MEDIA)
        db.session.add_all([org_com, org_auto, org_media])
        db.session.flush()

        result = get_organisation_for_noms_com()

        assert "Com Org 2" in result
        assert "Auto Org 3" in result
        assert "Media Org 3" not in result


class TestGetOrganisationChoicesFamily:
    """Test suite for get_organisation_choices_family function."""

    def test_returns_tuple_format(self, db: SQLAlchemy) -> None:
        """Test returns list of (name, name) tuples for HTML select."""
        org1 = Organisation(name="Choice Org 1", type=OrganisationTypeEnum.MEDIA)
        org2 = Organisation(name="Choice Org 2", type=OrganisationTypeEnum.MEDIA)
        db.session.add_all([org1, org2])
        db.session.flush()

        result = get_organisation_choices_family(OrganisationTypeEnum.MEDIA)

        assert ("Choice Org 1", "Choice Org 1") in result
        assert ("Choice Org 2", "Choice Org 2") in result

    def test_excludes_other_types_from_choices(self, db: SQLAlchemy) -> None:
        """Test excludes organisations of different types from choices."""
        # Create orgs of different types
        org1 = Organisation(
            name="Choice Exclude Media", type=OrganisationTypeEnum.MEDIA
        )
        org2 = Organisation(name="Choice Exclude COM", type=OrganisationTypeEnum.COM)
        db.session.add_all([org1, org2])
        db.session.flush()

        result = get_organisation_choices_family(OrganisationTypeEnum.OTHER)

        # Should not include the MEDIA or COM orgs we just created
        result_names = [item[0] for item in result]
        assert "Choice Exclude Media" not in result_names
        assert "Choice Exclude COM" not in result_names


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
        org1 = Organisation(name="Inviting Org 1", type=OrganisationTypeEnum.MEDIA)
        org2 = Organisation(name="Inviting Org 2", type=OrganisationTypeEnum.COM)
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
            name="KYC Case Test Org Unique", type=OrganisationTypeEnum.MEDIA
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
        assert result.type == OrganisationTypeEnum.AUTO

    def test_returns_existing_auto_org(self, db: SQLAlchemy) -> None:
        """Test returns existing AUTO org instead of creating duplicate."""
        existing_org = Organisation(
            name="Existing Auto", type=OrganisationTypeEnum.AUTO
        )
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
        media_org = Organisation(name="Dual Name Org", type=OrganisationTypeEnum.MEDIA)
        db.session.add(media_org)
        db.session.flush()

        user = User(email="store_auto_dual@example.com")
        profile = KYCProfile()
        user.profile = profile
        db.session.add_all([user, profile])
        db.session.flush()

        result = store_auto_organisation(user, org_name="Dual Name Org")

        assert result is not None
        assert result.type == OrganisationTypeEnum.AUTO
        assert result.id != media_org.id


class TestRetrieveUserOrganisation:
    """Test suite for retrieve_user_organisation function.

    Uses real survey profile IDs to control the organisation_field_name_origin
    property value.
    """

    def test_returns_inviting_org_when_name_matches(self, db: SQLAlchemy) -> None:
        """Test returns inviting organisation when name matches."""
        org = Organisation(name="Matching Org", type=OrganisationTypeEnum.MEDIA)
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
        assert result.type == OrganisationTypeEnum.AUTO


class TestSetNomGroupe:
    """Test suite for _set_nom_groupe helper function."""

    def test_sets_nom_groupe_for_pm_dir(self, db: SQLAlchemy) -> None:
        """Test sets nom_groupe from nom_groupe_presse for PM_DIR profile."""
        org = Organisation(name="Test Org Groupe", type=OrganisationTypeEnum.MEDIA)
        db.session.add(org)
        db.session.flush()

        info_pro = {"nom_groupe_presse": "Press Group"}
        _set_nom_groupe(org, ProfileEnum.PM_DIR, info_pro)

        assert org.nom_groupe == "Press Group"

    def test_sets_nom_groupe_for_pr_dir(self, db: SQLAlchemy) -> None:
        """Test sets nom_groupe from nom_group_com for PR_DIR profile."""
        org = Organisation(name="Test Org Groupe 2", type=OrganisationTypeEnum.COM)
        db.session.add(org)
        db.session.flush()

        info_pro = {"nom_group_com": "Com Group"}
        _set_nom_groupe(org, ProfileEnum.PR_DIR, info_pro)

        assert org.nom_groupe == "Com Group"

    def test_sets_nom_groupe_for_xp_dir(self, db: SQLAlchemy) -> None:
        """Test sets nom_groupe from nom_adm for XP_DIR_ANY profile."""
        org = Organisation(name="Test Org Groupe 3", type=OrganisationTypeEnum.OTHER)
        db.session.add(org)
        db.session.flush()

        info_pro = {"nom_adm": "Admin Group"}
        _set_nom_groupe(org, ProfileEnum.XP_DIR_ANY, info_pro)

        assert org.nom_groupe == "Admin Group"


class TestSetMediaTypes:
    """Test suite for _set_media_types helper function."""

    def test_sets_media_types_for_media_bw(self, db: SQLAlchemy) -> None:
        """Test sets media types for MEDIA business wall type."""
        org = Organisation(name="Media Type Org", type=OrganisationTypeEnum.MEDIA)
        db.session.add(org)
        db.session.flush()

        info_pro = {
            "type_entreprise_media": ["TV", "Radio"],
            "type_presse_et_media": ["National", "Regional"],
        }
        allowed_bw_types = {BWTypeEnum.MEDIA}
        _set_media_types(org, allowed_bw_types, info_pro)

        assert org.type_entreprise_media == ["TV", "Radio"]
        assert org.type_presse_et_media == ["National", "Regional"]

    def test_clears_media_types_for_non_media_bw(self, db: SQLAlchemy) -> None:
        """Test clears media types for non-MEDIA business wall type."""
        org = Organisation(name="Non Media Type Org", type=OrganisationTypeEnum.OTHER)
        db.session.add(org)
        db.session.flush()

        info_pro = {
            "type_entreprise_media": ["TV", "Radio"],
            "type_presse_et_media": ["National", "Regional"],
        }
        allowed_bw_types = {BWTypeEnum.ORGANISATION}
        _set_media_types(org, allowed_bw_types, info_pro)

        assert org.type_entreprise_media == []
        assert org.type_presse_et_media == []


class TestSetOrganizationTypes:
    """Test suite for _set_organization_types helper function."""

    def test_sets_agence_rp_for_pr_dir(self, db: SQLAlchemy) -> None:
        """Test sets type_agence_rp for PR_DIR profile."""
        org = Organisation(name="PR Org", type=OrganisationTypeEnum.COM)
        db.session.add(org)
        db.session.flush()

        info_pro = {
            "type_agence_rp": ["Conseil", "Relations presse"],
            "type_orga": [],
            "type_orga_detail": [],
        }
        allowed_bw_types = {BWTypeEnum.COM}
        _set_organization_types(org, ProfileEnum.PR_DIR, allowed_bw_types, info_pro)

        assert org.type_agence_rp == ["Conseil", "Relations presse"]

    def test_sets_type_orga_for_organisation_bw(self, db: SQLAlchemy) -> None:
        """Test sets type_organisation for ORGANISATION business wall type."""
        org = Organisation(name="Type Orga Org", type=OrganisationTypeEnum.OTHER)
        db.session.add(org)
        db.session.flush()

        info_pro = {
            "type_agence_rp": [],
            "type_orga": ["Association", "Fondation"],
            "type_orga_detail": ["Culture", "Education"],
        }
        allowed_bw_types = {BWTypeEnum.ORGANISATION}
        _set_organization_types(org, ProfileEnum.XP_DIR_ANY, allowed_bw_types, info_pro)

        assert org.type_organisation == ["Association", "Fondation"]
        assert org.type_organisation_detail == ["Culture", "Education"]


class TestSetActivitySectors:
    """Test suite for _set_activity_sectors helper function."""

    def test_sets_media_sectors(self, db: SQLAlchemy) -> None:
        """Test sets media activity sectors for MEDIA business wall type."""
        org = Organisation(name="Media Sectors Org", type=OrganisationTypeEnum.MEDIA)
        db.session.add(org)
        db.session.flush()

        info_mm = {
            "secteurs_activite_medias": ["Tech", "Finance"],
            "secteurs_activite_medias_detail": ["Startups", "Crypto"],
            "secteurs_activite_rp": [],
            "secteurs_activite_rp_detail": [],
            "secteurs_activite_detailles": [],
            "secteurs_activite_detailles_detail": [],
            "transformation_majeure": [],
            "transformation_majeure_detail": [],
        }
        allowed_bw_types = {BWTypeEnum.MEDIA}
        _set_activity_sectors(org, ProfileEnum.PM_DIR, allowed_bw_types, info_mm)

        assert org.secteurs_activite_medias == ["Tech", "Finance"]
        assert org.secteurs_activite_medias_detail == ["Startups", "Crypto"]

    def test_sets_rp_sectors(self, db: SQLAlchemy) -> None:
        """Test sets RP activity sectors for PR profiles."""
        org = Organisation(name="RP Sectors Org", type=OrganisationTypeEnum.COM)
        db.session.add(org)
        db.session.flush()

        info_mm = {
            "secteurs_activite_medias": [],
            "secteurs_activite_medias_detail": [],
            "secteurs_activite_rp": ["B2B", "B2C"],
            "secteurs_activite_rp_detail": ["Tech", "Consumer"],
            "secteurs_activite_detailles": [],
            "secteurs_activite_detailles_detail": [],
            "transformation_majeure": [],
            "transformation_majeure_detail": [],
        }
        allowed_bw_types = {BWTypeEnum.COM}
        _set_activity_sectors(org, ProfileEnum.PR_DIR, allowed_bw_types, info_mm)

        assert org.secteurs_activite_rp == ["B2B", "B2C"]
        assert org.secteurs_activite_rp_detail == ["Tech", "Consumer"]

    def test_sets_transformation_sectors(self, db: SQLAlchemy) -> None:
        """Test sets transformation sectors for TRANSFORMER business wall type."""
        org = Organisation(name="Transform Org", type=OrganisationTypeEnum.OTHER)
        db.session.add(org)
        db.session.flush()

        info_mm = {
            "secteurs_activite_medias": [],
            "secteurs_activite_medias_detail": [],
            "secteurs_activite_rp": [],
            "secteurs_activite_rp_detail": [],
            "secteurs_activite_detailles": ["Digital", "ESG"],
            "secteurs_activite_detailles_detail": ["Cloud", "Sustainability"],
            "transformation_majeure": ["IA", "Green"],
            "transformation_majeure_detail": ["Machine Learning", "Carbon Neutral"],
        }
        allowed_bw_types = {BWTypeEnum.TRANSFORMER}
        _set_activity_sectors(org, ProfileEnum.TP_DIR_ORG, allowed_bw_types, info_mm)

        assert org.secteurs_activite == ["Digital", "ESG"]
        assert org.transformation_majeure == ["IA", "Green"]


class TestSpecializeOrganizationType:
    """Test suite for specialize_organization_type function."""

    def test_specializes_media_org(self, db: SQLAlchemy) -> None:
        """Test specializes organisation for MEDIA profile."""
        org = Organisation(name="Specialize Media", type=OrganisationTypeEnum.MEDIA)
        db.session.add(org)
        db.session.flush()

        info_pro = {
            "nom_groupe_presse": "Media Group",
            "type_entreprise_media": ["TV"],
            "type_presse_et_media": ["National"],
            "type_agence_rp": [],
            "type_orga": [],
            "type_orga_detail": [],
        }
        info_mm = {
            "secteurs_activite_medias": ["Tech"],
            "secteurs_activite_medias_detail": ["AI"],
            "secteurs_activite_rp": [],
            "secteurs_activite_rp_detail": [],
            "secteurs_activite_detailles": [],
            "secteurs_activite_detailles_detail": [],
            "transformation_majeure": [],
            "transformation_majeure_detail": [],
        }

        specialize_organization_type(org, "PM_DIR", info_pro, info_mm)

        assert org.nom_groupe == "Media Group"
        assert org.type_entreprise_media == ["TV"]
        assert org.secteurs_activite_medias == ["Tech"]

    def test_specializes_com_org(self, db: SQLAlchemy) -> None:
        """Test specializes organisation for COM profile."""
        org = Organisation(name="Specialize Com", type=OrganisationTypeEnum.COM)
        db.session.add(org)
        db.session.flush()

        info_pro = {
            "nom_group_com": "Com Group",
            "type_entreprise_media": [],
            "type_presse_et_media": [],
            "type_agence_rp": ["Conseil"],
            "type_orga": [],
            "type_orga_detail": [],
        }
        info_mm = {
            "secteurs_activite_medias": [],
            "secteurs_activite_medias_detail": [],
            "secteurs_activite_rp": ["B2B"],
            "secteurs_activite_rp_detail": ["Tech"],
            "secteurs_activite_detailles": [],
            "secteurs_activite_detailles_detail": [],
            "transformation_majeure": [],
            "transformation_majeure_detail": [],
        }

        specialize_organization_type(org, "PR_DIR", info_pro, info_mm)

        assert org.nom_groupe == "Com Group"
        assert org.type_agence_rp == ["Conseil"]
        assert org.secteurs_activite_rp == ["B2B"]
