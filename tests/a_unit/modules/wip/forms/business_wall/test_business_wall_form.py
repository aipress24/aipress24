# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Tests for business_wall_form module.

This test file focuses on the testable utility functions and class initialization
logic. Tests verify state (returned forms, merged data) rather than behavior.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from flask_wtf import FlaskForm

from app.enums import BWTypeEnum, ProfileEnum
from app.models.auth import KYCProfile, User
from app.models.organisation import Organisation
from app.modules.wip.forms.business_wall.business_wall_form import (
    BWFormGenerator,
    bool_field,
    country_code_field,
    dual_multi_field,
    int_field,
    list_field,
    merge_org_results,
    multi_field,
    string_field,
    tel_field,
    textarea_field,
    url_field,
)

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


class TestFieldCreationFunctions:
    """Test suite for field creation utility functions."""

    def test_string_field_creates_field(self):
        """Test that string_field creates a Field object."""
        field = string_field("test_field", "Test Description")

        assert field is not None
        assert hasattr(field, "name")

    def test_string_field_mandatory(self):
        """Test string_field with mandatory flag."""
        field = string_field("test", "Test", mandatory=True)

        assert field is not None

    def test_string_field_readonly(self):
        """Test string_field with readonly flag."""
        field = string_field("test", "Test", readonly=True)

        assert field is not None

    def test_int_field_creates_field(self):
        """Test that int_field creates a Field object."""
        field = int_field("age", "Age")

        assert field is not None
        assert hasattr(field, "name")

    def test_int_field_mandatory(self):
        """Test int_field with mandatory flag."""
        field = int_field("count", "Count", mandatory=True)

        assert field is not None

    def test_bool_field_creates_field(self):
        """Test that bool_field creates a Field object."""
        field = bool_field("active", "Is Active")

        assert field is not None
        assert hasattr(field, "name")

    def test_textarea_field_creates_field(self):
        """Test that textarea_field creates a Field object."""
        field = textarea_field("description", "Description")

        assert field is not None
        assert hasattr(field, "name")

    def test_tel_field_creates_field(self):
        """Test that tel_field creates a Field object."""
        field = tel_field("phone", "Phone Number")

        assert field is not None
        assert hasattr(field, "name")

    def test_url_field_creates_field(self):
        """Test that url_field creates a Field object."""
        field = url_field("website", "Website URL")

        assert field is not None
        assert hasattr(field, "name")

    def test_list_field_creates_field(self):
        """Test that list_field creates a Field object."""
        # Use a valid ontology map that exists in the system
        field = list_field("categories", "Categories", ontology_map="list_taille_orga")

        assert field is not None
        assert hasattr(field, "name")

    def test_multi_field_creates_field(self):
        """Test that multi_field creates a Field object."""
        # Use a valid ontology map that exists in the system
        field = multi_field("tags", "Tags", ontology_map="multi_type_media")

        assert field is not None
        assert hasattr(field, "name")

    def test_dual_multi_field_creates_field(self):
        """Test that dual_multi_field creates a Field object."""
        # Use a valid ontology map that exists in the system
        field = dual_multi_field(
            "sectors", "Sectors", ontology_map="multidual_secteurs_detail"
        )

        assert field is not None
        assert hasattr(field, "name")

    def test_country_code_field_creates_field(self):
        """Test that country_code_field creates a Field object."""
        # Use a valid ontology map that exists in the system
        field = country_code_field("country", "Country", ontology_map="country_pays")

        assert field is not None
        assert hasattr(field, "name")


class TestBWFormGeneratorInitialization:
    """Test suite for BWFormGenerator class initialization."""

    def test_init_with_user(self, db_session: Session):
        """Test initialization with user argument."""
        user = User(email="test@example.com")
        user.photo = b""
        org = Organisation(name="Test Org")
        user.organisation = org
        db_session.add_all([user, org])
        db_session.flush()

        # Create profile for user
        profile = KYCProfile(
            user_id=user.id, profile_code="PM_DIR", profile_label="Test"
        )
        db_session.add(profile)
        db_session.flush()

        generator = BWFormGenerator(user=user)

        assert generator.org == org
        assert generator.profile_code == ProfileEnum.PM_DIR

    def test_init_with_org(self, db_session: Session):
        """Test initialization with org argument."""
        org = Organisation(name="Test Org", creator_profile_code="PM_DIR")
        db_session.add(org)
        db_session.flush()

        generator = BWFormGenerator(org=org)

        assert generator.org == org
        assert generator.profile_code == ProfileEnum.PM_DIR

    def test_init_without_args_raises_error(self):
        """Test that initialization without user or org raises ValueError."""
        with pytest.raises(ValueError, match="Missing user or organisation argument"):
            BWFormGenerator()

    def test_init_with_readonly(self, db_session: Session):
        """Test initialization with readonly flag."""
        org = Organisation(name="Test Org", creator_profile_code="PM_DIR")
        db_session.add(org)
        db_session.flush()

        generator = BWFormGenerator(org=org, readonly=True)

        assert generator.readonly is True

    def test_init_with_invalid_profile_code(self, db_session: Session):
        """Test initialization with invalid profile code falls back to default."""
        org = Organisation(name="Test Org", creator_profile_code="INVALID_CODE")
        db_session.add(org)
        db_session.flush()

        generator = BWFormGenerator(org=org)

        # Should fall back to PM_DIR
        assert generator.profile_code == ProfileEnum.PM_DIR

    def test_init_sets_creator_profile_from_user(self, db_session: Session):
        """Test that creator_profile_code is set from user profile when missing."""
        user = User(email="test@example.com")
        user.photo = b""
        org = Organisation(name="Test Org")
        user.organisation = org
        # Note: creator_profile_code is initially empty
        db_session.add_all([user, org])
        db_session.flush()

        profile = KYCProfile(
            user_id=user.id, profile_code="PM_JR_CP_SAL", profile_label="Test"
        )
        db_session.add(profile)
        db_session.flush()

        generator = BWFormGenerator(user=user)

        # Should have set creator_profile_code from user's profile
        assert org.creator_profile_code == "PM_JR_CP_SAL"
        assert generator.profile_code == ProfileEnum.PM_JR_CP_SAL


class TestBWFormGeneratorGenerate:
    """Test suite for BWFormGenerator.generate() method.

    Tests verify that generate() returns a valid FlaskForm for each bw_type.
    State-based testing: we check the returned form, not which internal
    methods were called.
    """

    def test_generate_with_no_bw_type(self, db_session: Session):
        """Test generate() with org that has no bw_type returns empty form."""
        org = Organisation(name="Test Org", creator_profile_code="PM_DIR")
        org.bw_type = None
        db_session.add(org)
        db_session.flush()

        generator = BWFormGenerator(org=org)
        form = generator.generate()

        # Should return a FlaskForm (possibly empty)
        assert isinstance(form, FlaskForm)

    def test_generate_with_agency_type_returns_form(self, db_session: Session):
        """Test generate() with AGENCY bw_type returns a valid form."""
        org = Organisation(name="Test Org", creator_profile_code="PM_DIR")
        org.bw_type = BWTypeEnum.AGENCY
        db_session.add(org)
        db_session.flush()

        generator = BWFormGenerator(org=org)
        form = generator.generate()

        assert isinstance(form, FlaskForm)

    def test_generate_with_media_type_returns_form(self, db_session: Session):
        """Test generate() with MEDIA bw_type returns a valid form."""
        org = Organisation(name="Test Org", creator_profile_code="PM_DIR")
        org.bw_type = BWTypeEnum.MEDIA
        db_session.add(org)
        db_session.flush()

        generator = BWFormGenerator(org=org)
        form = generator.generate()

        assert isinstance(form, FlaskForm)

    def test_generate_with_micro_type_returns_form(self, db_session: Session):
        """Test generate() with MICRO bw_type returns a valid form."""
        org = Organisation(name="Test Org", creator_profile_code="PM_DIR")
        org.bw_type = BWTypeEnum.MICRO
        db_session.add(org)
        db_session.flush()

        generator = BWFormGenerator(org=org)
        form = generator.generate()

        assert isinstance(form, FlaskForm)

    def test_generate_with_corporate_type_returns_form(self, db_session: Session):
        """Test generate() with CORPORATE bw_type returns a valid form."""
        org = Organisation(name="Test Org", creator_profile_code="PM_DIR")
        org.bw_type = BWTypeEnum.CORPORATE
        db_session.add(org)
        db_session.flush()

        generator = BWFormGenerator(org=org)
        form = generator.generate()

        assert isinstance(form, FlaskForm)

    def test_generate_with_pressunion_type_returns_form(self, db_session: Session):
        """Test generate() with PRESSUNION bw_type returns a valid form."""
        org = Organisation(name="Test Org", creator_profile_code="PM_DIR")
        org.bw_type = BWTypeEnum.PRESSUNION
        db_session.add(org)
        db_session.flush()

        generator = BWFormGenerator(org=org)
        form = generator.generate()

        assert isinstance(form, FlaskForm)

    def test_generate_with_com_type_returns_form(self, db_session: Session):
        """Test generate() with COM bw_type returns a valid form."""
        org = Organisation(name="Test Org", creator_profile_code="PM_DIR")
        org.bw_type = BWTypeEnum.COM
        db_session.add(org)
        db_session.flush()

        generator = BWFormGenerator(org=org)
        form = generator.generate()

        assert isinstance(form, FlaskForm)

    def test_generate_with_organisation_type_returns_form(self, db_session: Session):
        """Test generate() with ORGANISATION bw_type returns a valid form."""
        org = Organisation(name="Test Org", creator_profile_code="PM_DIR")
        org.bw_type = BWTypeEnum.ORGANISATION
        db_session.add(org)
        db_session.flush()

        generator = BWFormGenerator(org=org)
        form = generator.generate()

        assert isinstance(form, FlaskForm)

    def test_generate_with_transformer_type_returns_form(self, db_session: Session):
        """Test generate() with TRANSFORMER bw_type returns a valid form."""
        org = Organisation(name="Test Org", creator_profile_code="PM_DIR")
        org.bw_type = BWTypeEnum.TRANSFORMER
        db_session.add(org)
        db_session.flush()

        generator = BWFormGenerator(org=org)
        form = generator.generate()

        assert isinstance(form, FlaskForm)

    def test_generate_with_academics_type_returns_form(self, db_session: Session):
        """Test generate() with ACADEMICS bw_type returns a valid form."""
        org = Organisation(name="Test Org", creator_profile_code="PM_DIR")
        org.bw_type = BWTypeEnum.ACADEMICS
        db_session.add(org)
        db_session.flush()

        generator = BWFormGenerator(org=org)
        form = generator.generate()

        assert isinstance(form, FlaskForm)


class TestMergeOrgResults:
    """Test suite for merge_org_results function."""

    def test_merge_simple_string_field(self, db_session: Session):
        """Test merging simple string field."""
        org = Organisation(name="Old Name")
        db_session.add(org)
        db_session.flush()

        results = {"name": ["New Name"]}
        merge_org_results(org, results)

        assert org.name == "New Name"

    def test_merge_empty_string_field(self, db_session: Session):
        """Test merging empty string field."""
        org = Organisation(name="Old Name")
        db_session.add(org)
        db_session.flush()

        results = {"name": []}
        merge_org_results(org, results)

        assert org.name == ""

    def test_merge_bool_field_true(self, db_session: Session):
        """Test merging boolean field with true value."""
        org = Organisation(name="Test", agree_arcom=False)
        db_session.add(org)
        db_session.flush()

        results = {"agree_arcom": [True]}
        merge_org_results(org, results)

        assert org.agree_arcom is True

    def test_merge_bool_field_false(self, db_session: Session):
        """Test merging boolean field with false value."""
        org = Organisation(name="Test", agree_arcom=True)
        db_session.add(org)
        db_session.flush()

        results = {"agree_arcom": [False]}
        merge_org_results(org, results)

        assert org.agree_arcom is False

    def test_merge_bool_field_empty(self, db_session: Session):
        """Test merging empty boolean field defaults to False."""
        org = Organisation(name="Test", agree_arcom=True)
        db_session.add(org)
        db_session.flush()

        results = {"agree_arcom": []}
        merge_org_results(org, results)

        assert org.agree_arcom is False

    def test_merge_int_field(self, db_session: Session):
        """Test merging integer field."""
        org = Organisation(name="Test")
        db_session.add(org)
        db_session.flush()

        results = {"number_customers": ["42"]}
        merge_org_results(org, results)

        assert org.number_customers == 42

    def test_merge_int_field_invalid_defaults_zero(self, db_session: Session):
        """Test merging invalid integer field defaults to 0."""
        org = Organisation(name="Test", number_customers=10)
        db_session.add(org)
        db_session.flush()

        results = {"number_customers": ["not-a-number"]}
        merge_org_results(org, results)

        assert org.number_customers == 0

    def test_merge_int_field_empty_defaults_zero(self, db_session: Session):
        """Test merging empty integer field defaults to 0."""
        org = Organisation(name="Test", number_customers=10)
        db_session.add(org)
        db_session.flush()

        results = {"number_customers": []}
        merge_org_results(org, results)

        assert org.number_customers == 0

    def test_merge_list_field(self, db_session: Session):
        """Test merging list field."""
        org = Organisation(name="Test")
        db_session.add(org)
        db_session.flush()

        results = {"type_presse_et_media": ["Type1", "Type2", "Type3"]}
        merge_org_results(org, results)

        assert org.type_presse_et_media == ["Type1", "Type2", "Type3"]

    def test_merge_empty_list_field(self, db_session: Session):
        """Test merging empty list field."""
        org = Organisation(name="Test", type_presse_et_media=["Old"])
        db_session.add(org)
        db_session.flush()

        results = {"type_presse_et_media": []}
        merge_org_results(org, results)

        assert org.type_presse_et_media == []

    def test_merge_multiple_fields(self, db_session: Session):
        """Test merging multiple fields at once."""
        org = Organisation(name="Old")
        db_session.add(org)
        db_session.flush()

        results = {
            "name": ["New Name"],
            "siren": ["123456789"],
            "agree_arcom": [True],
            "number_customers": ["50"],
            "type_presse_et_media": ["Type1", "Type2"],
        }
        merge_org_results(org, results)

        assert org.name == "New Name"
        assert org.siren == "123456789"
        assert org.agree_arcom is True
        assert org.number_customers == 50
        assert org.type_presse_et_media == ["Type1", "Type2"]

    def test_merge_resets_unmentioned_fields(self, db_session: Session):
        """Test that merge resets fields not in results to defaults.

        Note: merge_org_results assigns ALL fields, even those not in results.
        Fields not in results get default values (empty string, empty list, etc.)
        """
        org = Organisation(
            name="Original",
            siren="999999999",
            tva="FR12345",
        )
        db_session.add(org)
        db_session.flush()

        results = {"name": ["New Name"]}
        merge_org_results(org, results)

        assert org.name == "New Name"
        # Fields not in results are reset to empty strings
        assert org.siren == ""
        assert org.tva == ""
