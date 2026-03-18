# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Integration tests for Business Wall form generation and field helpers."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from flask_wtf import FlaskForm

from app.enums import BWTypeEnum, ProfileEnum
from app.models.auth import KYCProfile, User
from app.models.organisation import Organisation
from app.modules.wip.forms.business_wall.business_wall_fields import (
    TAG_MANDATORY,
    TAG_PHOTO_FORMAT,
    _filter_mandatory_label,
    _filter_photo_format,
    custom_bw_logo_field,
)
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
from app.modules.wip.forms.business_wall.valid_bw_image import (
    ValidBWImageField,
)

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


# ============================================================================
# Test fixtures
# ============================================================================


@pytest.fixture
def org_media(db_session: Session) -> Organisation:
    """Create an organisation with MEDIA bw_type."""
    org = Organisation(
        name="Test Media Org",
        bw_type=BWTypeEnum.MEDIA,
        creator_profile_code=ProfileEnum.PM_DIR.name,
    )
    db_session.add(org)
    db_session.flush()
    return org


@pytest.fixture
def org_com(db_session: Session) -> Organisation:
    """Create an organisation with COM bw_type."""
    org = Organisation(
        name="Test PR Agency",
        bw_type=BWTypeEnum.COM,
        creator_profile_code=ProfileEnum.PR_DIR.name,
    )
    db_session.add(org)
    db_session.flush()
    return org


@pytest.fixture
def org_agency(db_session: Session) -> Organisation:
    """Create an organisation with AGENCY bw_type."""
    org = Organisation(
        name="Test Agency",
        bw_type=BWTypeEnum.AGENCY,
        creator_profile_code=ProfileEnum.PM_DIR.name,
    )
    db_session.add(org)
    db_session.flush()
    return org


@pytest.fixture
def org_corporate(db_session: Session) -> Organisation:
    """Create an organisation with CORPORATE bw_type."""
    org = Organisation(
        name="Test Corporate Media",
        bw_type=BWTypeEnum.CORPORATE,
        creator_profile_code=ProfileEnum.PM_DIR.name,
    )
    db_session.add(org)
    db_session.flush()
    return org


@pytest.fixture
def org_transformer(db_session: Session) -> Organisation:
    """Create an organisation with TRANSFORMER bw_type."""
    org = Organisation(
        name="Test Transformer",
        bw_type=BWTypeEnum.TRANSFORMER,
        creator_profile_code=ProfileEnum.TP_DIR_ORG.name,
    )
    db_session.add(org)
    db_session.flush()
    return org


@pytest.fixture
def org_academics(db_session: Session) -> Organisation:
    """Create an organisation with ACADEMICS bw_type."""
    org = Organisation(
        name="Test University",
        bw_type=BWTypeEnum.ACADEMICS,
        creator_profile_code=ProfileEnum.AC_DIR.name,
    )
    db_session.add(org)
    db_session.flush()
    return org


@pytest.fixture
def org_organisation(db_session: Session) -> Organisation:
    """Create an organisation with ORGANISATION bw_type."""
    org = Organisation(
        name="Test Organisation",
        bw_type=BWTypeEnum.ORGANISATION,
        creator_profile_code=ProfileEnum.XP_DIR_ANY.name,
    )
    db_session.add(org)
    db_session.flush()
    return org


@pytest.fixture
def org_pressunion(db_session: Session) -> Organisation:
    """Create an organisation with PRESSUNION bw_type."""
    org = Organisation(
        name="Test Press Union",
        bw_type=BWTypeEnum.PRESSUNION,
        creator_profile_code=ProfileEnum.PM_DIR.name,
    )
    db_session.add(org)
    db_session.flush()
    return org


@pytest.fixture
def org_micro(db_session: Session) -> Organisation:
    """Create an organisation with MICRO bw_type."""
    org = Organisation(
        name="Test Micro Media",
        bw_type=BWTypeEnum.MICRO,
        creator_profile_code=ProfileEnum.PM_JR_PIG.name,
    )
    db_session.add(org)
    db_session.flush()
    return org


@pytest.fixture
def user_with_org(db_session: Session, org_media: Organisation) -> User:
    """Create a user with organisation."""
    profile = KYCProfile(profile_code=ProfileEnum.PM_DIR.name)
    user = User(
        email="formtest@example.com",
        first_name="Form",
        last_name="Tester",
        active=True,
    )
    user.profile = profile
    user.organisation = org_media
    user.organisation_id = org_media.id
    db_session.add(user)
    db_session.flush()
    return user


# ============================================================================
# Tests for business_wall_fields.py
# ============================================================================


class TestFilterMandatoryLabel:
    """Tests for _filter_mandatory_label function."""

    def test_adds_mandatory_tag_when_true(self):
        """Test that mandatory tag is added when code is True."""
        result = _filter_mandatory_label("Field name", True)

        assert TAG_MANDATORY in result
        assert result == f"Field name {TAG_MANDATORY}"

    def test_no_tag_when_false(self):
        """Test that no tag is added when code is False."""
        result = _filter_mandatory_label("Field name", False)

        assert TAG_MANDATORY not in result
        assert result == "Field name"


class TestFilterPhotoFormat:
    """Tests for _filter_photo_format function."""

    def test_adds_photo_format_tag(self):
        """Test that photo format tag is always added."""
        result = _filter_photo_format("Logo")

        assert TAG_PHOTO_FORMAT in result
        assert result == f"Logo {TAG_PHOTO_FORMAT}"


class TestCustomBwLogoField:
    """Tests for custom_bw_logo_field function."""

    def test_creates_valid_bw_image_field(self):
        """Test that function creates a ValidBWImageField."""
        field = custom_bw_logo_field(
            name="test_logo",
            description="Test Logo",
            mandatory=False,
            readonly=False,
        )

        # UnboundField wraps the actual field class
        assert field is not None

    def test_mandatory_field_has_kyc_code_m(self):
        """Test that mandatory field has kyc_code 'M'."""
        field = custom_bw_logo_field(
            name="test_logo",
            description="Test Logo",
            mandatory=True,
            readonly=False,
        )

        assert field is not None

    def test_readonly_field_has_readonly_1(self):
        """Test that readonly field has readonly=1."""
        field = custom_bw_logo_field(
            name="test_logo",
            description="Test Logo",
            mandatory=False,
            readonly=True,
        )

        assert field is not None


# ============================================================================
# Tests for valid_bw_image.py
# ============================================================================


class TestValidBWImageField:
    """Tests for ValidBWImageField class.

    Note: WTForms fields need to be bound to a form to be fully initialized.
    These tests create a form class to test the field behavior.
    """

    def test_field_initialization(self, app):
        """Test field can be initialized with default values."""
        with app.app_context():

            class TestForm(FlaskForm):
                image = ValidBWImageField(label="Test Image")

            form = TestForm()
            field = form.image

            assert field.max_image_size == 2048
            assert field.is_required is False
            assert field.readonly is False
            assert field.file_object is None
            assert field.multiple is False

    def test_field_with_custom_max_size(self, app):
        """Test field respects custom max_image_size."""
        with app.app_context():

            class TestForm(FlaskForm):
                image = ValidBWImageField(label="Test Image", max_image_size=4096)

            form = TestForm()
            assert form.image.max_image_size == 4096

    def test_preload_filename_empty_without_file_object(self, app):
        """Test preload_filename returns empty string without file_object."""
        with app.app_context():

            class TestForm(FlaskForm):
                image = ValidBWImageField(label="Test Image")

            form = TestForm()
            assert form.image.preload_filename == ""

    def test_preload_filesize_zero_without_file_object(self, app):
        """Test preload_filesize returns 0 without file_object."""
        with app.app_context():

            class TestForm(FlaskForm):
                image = ValidBWImageField(label="Test Image")

            form = TestForm()
            assert form.image.preload_filesize == 0

    def test_get_image_url_none_without_file_object(self, app):
        """Test get_image_url returns None without file_object."""
        with app.app_context():

            class TestForm(FlaskForm):
                image = ValidBWImageField(label="Test Image")

            form = TestForm()
            assert form.image.get_image_url() is None

    def test_id_preload_name(self, app):
        """Test id_preload_name returns correct format."""
        with app.app_context():

            class TestForm(FlaskForm):
                test_field = ValidBWImageField(label="Test Image")

            form = TestForm()
            # The field's id matches the attribute name
            assert form.test_field.id_preload_name() == "test_field_preload_name"

    def test_name_preload_name(self, app):
        """Test name_preload_name returns correct format."""
        with app.app_context():

            class TestForm(FlaskForm):
                test_field = ValidBWImageField(label="Test Image")

            form = TestForm()
            assert form.test_field.name_preload_name() == "test_field_preload_name"


# ============================================================================
# Tests for business_wall_form.py - Field helpers
# ============================================================================


class TestFieldHelpers:
    """Tests for field helper functions."""

    def test_string_field_creates_unbound_field(self):
        """Test string_field creates an UnboundField."""
        field = string_field("test_name", "Test Description")

        assert field is not None

    def test_int_field_creates_unbound_field(self):
        """Test int_field creates an UnboundField."""
        field = int_field("test_int", "Test Int Field")

        assert field is not None

    def test_bool_field_creates_unbound_field(self):
        """Test bool_field creates an UnboundField."""
        field = bool_field("test_bool", "Test Bool Field")

        assert field is not None

    def test_textarea_field_creates_unbound_field(self):
        """Test textarea_field creates an UnboundField."""
        field = textarea_field("test_textarea", "Test Textarea")

        assert field is not None

    def test_tel_field_creates_unbound_field(self):
        """Test tel_field creates an UnboundField."""
        field = tel_field("test_tel", "Test Phone")

        assert field is not None

    def test_url_field_creates_unbound_field(self):
        """Test url_field creates an UnboundField."""
        field = url_field("test_url", "Test URL")

        assert field is not None

    def test_list_field_creates_unbound_field(self):
        """Test list_field creates an UnboundField."""
        field = list_field("test_list", "Test List", ontology_map="list_taille_orga")

        assert field is not None

    def test_multi_field_creates_unbound_field(self):
        """Test multi_field creates an UnboundField."""
        field = multi_field("test_multi", "Test Multi", ontology_map="multi_type_media")

        assert field is not None

    def test_dual_multi_field_creates_unbound_field(self):
        """Test dual_multi_field creates an UnboundField."""
        field = dual_multi_field(
            "test_dual", "Test Dual", ontology_map="multidual_secteurs_detail"
        )

        assert field is not None

    def test_country_code_field_creates_unbound_field(self):
        """Test country_code_field creates an UnboundField."""
        field = country_code_field(
            "test_country", "Test Country", ontology_map="country_pays"
        )

        assert field is not None


# ============================================================================
# Tests for BWFormGenerator
# ============================================================================


class TestBWFormGeneratorInit:
    """Tests for BWFormGenerator initialization."""

    def test_init_with_user(self, app, user_with_org: User):
        """Test initialization with user."""
        with app.app_context():
            generator = BWFormGenerator(user=user_with_org)

            assert generator.org == user_with_org.organisation
            assert generator.readonly is False

    def test_init_with_org(self, app, org_media: Organisation):
        """Test initialization with organisation directly."""
        with app.app_context():
            generator = BWFormGenerator(org=org_media)

            assert generator.org == org_media

    def test_init_readonly(self, app, org_media: Organisation):
        """Test initialization with readonly=True."""
        with app.app_context():
            generator = BWFormGenerator(org=org_media, readonly=True)

            assert generator.readonly is True

    def test_init_without_user_or_org_raises(self, app):
        """Test initialization without user or org raises ValueError."""
        with app.app_context():
            with pytest.raises(ValueError, match="Missing user or organisation"):
                BWFormGenerator()


class TestBWFormGeneratorGenerate:
    """Tests for BWFormGenerator.generate method."""

    def test_generate_media_form(self, app, org_media: Organisation):
        """Test generating form for MEDIA bw_type."""
        with app.app_context():
            generator = BWFormGenerator(org=org_media)
            form = generator.generate()

            assert isinstance(form, FlaskForm)
            assert hasattr(form, "name")
            assert hasattr(form, "siren")

    def test_generate_com_form(self, app, org_com: Organisation):
        """Test generating form for COM bw_type."""
        with app.app_context():
            generator = BWFormGenerator(org=org_com)
            form = generator.generate()

            assert isinstance(form, FlaskForm)
            assert hasattr(form, "name")
            assert hasattr(form, "type_agence_rp")

    def test_generate_agency_form(self, app, org_agency: Organisation):
        """Test generating form for AGENCY bw_type."""
        with app.app_context():
            generator = BWFormGenerator(org=org_agency)
            form = generator.generate()

            assert isinstance(form, FlaskForm)
            assert hasattr(form, "name")

    def test_generate_corporate_form(self, app, org_corporate: Organisation):
        """Test generating form for CORPORATE bw_type."""
        with app.app_context():
            generator = BWFormGenerator(org=org_corporate)
            form = generator.generate()

            assert isinstance(form, FlaskForm)
            assert hasattr(form, "name")

    def test_generate_transformer_form(self, app, org_transformer: Organisation):
        """Test generating form for TRANSFORMER bw_type."""
        with app.app_context():
            generator = BWFormGenerator(org=org_transformer)
            form = generator.generate()

            assert isinstance(form, FlaskForm)
            assert hasattr(form, "name")
            assert hasattr(form, "transformation_majeure")

    def test_generate_academics_form(self, app, org_academics: Organisation):
        """Test generating form for ACADEMICS bw_type."""
        with app.app_context():
            generator = BWFormGenerator(org=org_academics)
            form = generator.generate()

            assert isinstance(form, FlaskForm)
            assert hasattr(form, "name")

    def test_generate_organisation_form(self, app, org_organisation: Organisation):
        """Test generating form for ORGANISATION bw_type."""
        with app.app_context():
            generator = BWFormGenerator(org=org_organisation)
            form = generator.generate()

            assert isinstance(form, FlaskForm)
            assert hasattr(form, "name")
            assert hasattr(form, "type_organisation")

    def test_generate_pressunion_form(self, app, org_pressunion: Organisation):
        """Test generating form for PRESSUNION bw_type."""
        with app.app_context():
            generator = BWFormGenerator(org=org_pressunion)
            form = generator.generate()

            assert isinstance(form, FlaskForm)
            assert hasattr(form, "name")

    def test_generate_micro_form(self, app, org_micro: Organisation):
        """Test generating form for MICRO bw_type."""
        with app.app_context():
            generator = BWFormGenerator(org=org_micro)
            form = generator.generate()

            assert isinstance(form, FlaskForm)
            assert hasattr(form, "name")

    def test_generate_none_form(self, app, db_session: Session):
        """Test generating form for None bw_type."""
        org = Organisation(
            name="No BW Org",
            bw_type=None,
            creator_profile_code=ProfileEnum.PM_DIR.name,
        )
        db_session.add(org)
        db_session.flush()

        with app.app_context():
            generator = BWFormGenerator(org=org)
            form = generator.generate()

            assert isinstance(form, FlaskForm)


# ============================================================================
# Tests for merge_org_results
# ============================================================================


class TestMergeOrgResults:
    """Tests for merge_org_results function."""

    def test_merge_basic_fields(self, org_media: Organisation):
        """Test merging basic string fields."""
        results = {
            "name": ["New Media Name"],
            "siren": ["123456789"],
            "tva": ["FR12345678901"],
            "description": ["New description"],
        }

        merge_org_results(org_media, results)

        assert org_media.name == "New Media Name"
        assert org_media.siren == "123456789"
        assert org_media.tva == "FR12345678901"
        assert org_media.description == "New description"

    def test_merge_empty_values(self, org_media: Organisation):
        """Test merging with empty values."""
        results: dict = {
            "name": [],
            "siren": [],
        }

        merge_org_results(org_media, results)

        assert org_media.name == ""
        assert org_media.siren == ""

    def test_merge_boolean_fields(self, org_media: Organisation):
        """Test merging boolean fields."""
        results = {
            "agree_arcom": [True],
            "agree_cppap": [False],
            "membre_sapi": [],  # Empty should be False
        }

        merge_org_results(org_media, results)

        assert org_media.agree_arcom is True
        assert org_media.agree_cppap is False
        assert org_media.membre_sapi is False

    def test_merge_integer_field(self, org_media: Organisation):
        """Test merging integer field."""
        results = {
            "number_customers": ["42"],
        }

        merge_org_results(org_media, results)

        assert org_media.number_customers == 42

    def test_merge_invalid_integer_defaults_to_zero(self, org_media: Organisation):
        """Test merging invalid integer defaults to 0."""
        results = {
            "number_customers": ["not_a_number"],
        }

        merge_org_results(org_media, results)

        assert org_media.number_customers == 0

    def test_merge_list_fields(self, org_media: Organisation):
        """Test merging list fields."""
        results = {
            "secteurs_activite_medias": ["Tech", "Finance"],
            "secteurs_activite_medias_detail": ["Tech > Software", "Finance > Banking"],
        }

        merge_org_results(org_media, results)

        assert org_media.secteurs_activite_medias == ["Tech", "Finance"]
        assert org_media.secteurs_activite_medias_detail == [
            "Tech > Software",
            "Finance > Banking",
        ]

    def test_merge_clears_metiers_fields(self, org_media: Organisation):
        """Test that metiers fields are always cleared."""
        org_media.metiers_presse = ["Old metier"]
        org_media.metiers = ["Old metier 2"]

        results: dict = {}

        merge_org_results(org_media, results)

        assert org_media.metiers_presse == []
        assert org_media.metiers == []
        assert org_media.metiers_detail == []
