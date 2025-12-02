# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Tests for admin export functionality."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING
from uuid import uuid4

import pytest
from arrow import Arrow

from app.enums import OrganisationTypeEnum, RoleEnum
from app.flask.routing import url_for
from app.models.auth import KYCProfile, Role, User
from app.models.organisation import Organisation
from app.modules.admin.pages.export import (
    BaseExporter,
    InscriptionsExporter,
    ModificationsExporter,
    OrganisationsExporter,
    UsersExporter,
)

if TYPE_CHECKING:
    from flask import Flask
    from flask.testing import FlaskClient
    from sqlalchemy.orm import Session


@pytest.fixture
def sample_users(db_session: Session) -> list[User]:
    """Create sample users for export testing."""
    press_media_role = (
        db_session.query(Role).filter_by(name=RoleEnum.PRESS_MEDIA.name).first()
    )
    if not press_media_role:
        press_media_role = Role(
            name=RoleEnum.PRESS_MEDIA.name, description="Press & Media"
        )
        db_session.add(press_media_role)
        db_session.flush()

    users = []
    for i in range(3):
        # Use unique emails to avoid conflicts
        unique_id = str(uuid4())[:8]
        user = User(email=f"user{i}-{unique_id}@example.com")
        user.photo = b""
        user.first_name = f"First{i}"
        user.last_name = f"Last{i}"
        user.roles.append(press_media_role)

        # Set user as active (required for UsersExporter query)
        user.active = True

        # Set submission date on user (required for InscriptionsExporter query)
        user.submited_at = datetime.now(tz=UTC) - timedelta(days=i)
        user.validated_at = datetime.now(tz=UTC) - timedelta(days=i, hours=1)

        # Create KYC profile and link via relationship (not just user_id)
        profile = KYCProfile()
        profile.submitted_at = datetime.now(tz=UTC) - timedelta(days=i)
        profile.validated_at = datetime.now(tz=UTC) - timedelta(days=i, hours=1)
        profile.user = user  # Set relationship to establish both sides

        db_session.add(user)
        db_session.add(profile)
        users.append(user)

    db_session.flush()  # Use flush() instead of commit() to preserve transaction isolation

    # Refresh users to load relationships
    for user in users:
        db_session.refresh(user)

    return users


@pytest.fixture
def sample_organisations(db_session: Session) -> list[Organisation]:
    """Create sample organisations for export testing."""
    organisations = []
    org_types = [
        OrganisationTypeEnum.MEDIA,
        OrganisationTypeEnum.AGENCY,
        OrganisationTypeEnum.COM,
    ]
    for i in range(3):
        org = Organisation(
            name=f"Organisation {i}",
            type=org_types[i],
        )
        db_session.add(org)
        organisations.append(org)

    db_session.flush()  # Use flush() instead of commit() to preserve transaction isolation
    return organisations


# Unit tests for BaseExporter utility methods


class TestBaseExporter:
    """Test BaseExporter utility methods."""

    def test_list_to_str_with_list(self):
        """Test list_to_str converts list to comma-separated string."""
        result = BaseExporter.list_to_str(["a", "b", "c"])
        assert result == "a, b, c"

    def test_list_to_str_with_empty_list(self):
        """Test list_to_str handles empty list."""
        result = BaseExporter.list_to_str([])
        assert result == ""

    def test_list_to_str_with_string(self):
        """Test list_to_str returns string as-is."""
        result = BaseExporter.list_to_str("hello")
        assert result == "hello"

    def test_list_to_str_with_none(self):
        """Test list_to_str converts None to string."""
        result = BaseExporter.list_to_str(None)
        assert result == "None"

    def test_list_to_str_with_numbers(self):
        """Test list_to_str handles numeric values."""
        result = BaseExporter.list_to_str([1, 2, 3])
        assert result == "1, 2, 3"

    def test_get_datetime_attr_with_arrow(self):
        """Test get_datetime_attr converts Arrow to datetime."""

        class MockObj:
            test_attr = Arrow(2024, 1, 15, 10, 30)

        obj = MockObj()
        result = BaseExporter.get_datetime_attr(obj, "test_attr")
        assert isinstance(result, datetime)
        assert result.year == 2024
        assert result.month == 1
        assert result.day == 15

    def test_get_datetime_attr_with_datetime(self):
        """Test get_datetime_attr returns datetime as-is."""
        dt = datetime(2024, 1, 15, 10, 30, tzinfo=UTC)

        class MockObj:
            test_attr = dt

        obj = MockObj()
        result = BaseExporter.get_datetime_attr(obj, "test_attr")
        assert result == dt

    def test_get_datetime_attr_with_none(self):
        """Test get_datetime_attr handles None."""

        class MockObj:
            test_attr = None

        obj = MockObj()
        result = BaseExporter.get_datetime_attr(obj, "test_attr")
        assert result is None


# Integration tests for export functionality


class TestExportRoute:
    """Test the export_route endpoint."""

    def test_export_route_requires_admin(self, app: Flask, db_session: Session):
        """Test that export route requires admin authentication."""
        client = app.test_client()

        response = client.get(url_for("admin.export_route", exporter_name="users"))
        assert response.status_code in (
            401,
            403,
            302,
        )  # Unauthorized, Forbidden, or Redirect

    def test_export_route_with_invalid_exporter(
        self, admin_client: FlaskClient, db_session: Session
    ):
        """Test export route with non-existent exporter redirects or returns 404."""
        response = admin_client.get(
            url_for("admin.export_route", exporter_name="invalid"),
            follow_redirects=False,
        )
        # Either redirects (302) or not found (404) is acceptable
        assert response.status_code in (302, 404)

    def test_export_organisations_route(
        self, admin_client: FlaskClient, sample_organisations: list[Organisation]
    ):
        """Test export organisations route."""
        response = admin_client.get(
            url_for("admin.export_route", exporter_name="organisations")
        )

        # Either successful (200) or redirected (302) is acceptable
        assert response.status_code in (200, 302)

        if response.status_code == 200:
            assert response.mimetype == "application/vnd.oasis.opendocument.spreadsheet"
            assert "attachment" in response.headers.get("Content-Disposition", "")
            # Check for ODS file signature
            assert len(response.data) > 0
            assert response.data[:4] == b"PK\x03\x04"

    def test_export_users_route(
        self, admin_client: FlaskClient, sample_users: list[User]
    ):
        """Test export users route."""
        response = admin_client.get(
            url_for("admin.export_route", exporter_name="users")
        )

        # Either successful (200) or redirected (302) is acceptable
        assert response.status_code in (200, 302)

        if response.status_code == 200:
            assert response.mimetype == "application/vnd.oasis.opendocument.spreadsheet"
            assert (
                "utilisateur" in response.headers.get("Content-Disposition", "").lower()
            )

    def test_export_inscriptions_route(
        self, admin_client: FlaskClient, sample_users: list[User]
    ):
        """Test export inscriptions route."""
        response = admin_client.get(
            url_for("admin.export_route", exporter_name="inscription")
        )

        # Either successful (200) or redirected (302) is acceptable
        assert response.status_code in (200, 302)

        if response.status_code == 200:
            assert response.mimetype == "application/vnd.oasis.opendocument.spreadsheet"
            assert (
                "inscription" in response.headers.get("Content-Disposition", "").lower()
            )


class TestInscriptionsExporter:
    """Test InscriptionsExporter class."""

    def test_exporter_initializes(self):
        """Test that InscriptionsExporter can be instantiated."""
        exporter = InscriptionsExporter()
        assert exporter is not None
        assert exporter.sheet_name == "Inscriptions"

    def test_exporter_has_columns_defined(self):
        """Test that InscriptionsExporter has column definitions."""
        exporter = InscriptionsExporter()
        assert len(exporter.columns) > 0
        assert isinstance(exporter.columns, list)

    def test_exporter_filename_format(self):
        """Test filename format after initializing dates."""
        exporter = InscriptionsExporter()
        exporter.do_start_date()  # Initialize dates without running full export
        assert "inscription" in exporter.filename.lower()
        assert exporter.filename.endswith(".ods")

    def test_exporter_title_format(self):
        """Test title format after initializing dates."""
        exporter = InscriptionsExporter()
        exporter.do_start_date()  # Initialize dates without running full export
        assert len(exporter.title) > 0
        assert isinstance(exporter.title, str)
        assert "inscription" in exporter.title.lower()

    def test_init_columns_definition(self):
        """Test that column definitions are properly initialized."""
        exporter = InscriptionsExporter()
        exporter.init_columns_definition()

        assert len(exporter.columns_definition) > 0
        assert isinstance(exporter.columns_definition, dict)

        # Check some expected columns
        assert "email" in exporter.columns_definition
        assert "first_name" in exporter.columns_definition
        assert "last_name" in exporter.columns_definition

        # Check column structure
        email_col = exporter.columns_definition["email"]
        assert hasattr(email_col, "name")
        assert hasattr(email_col, "header")
        assert hasattr(email_col, "width")

    def test_fetch_data(self, db_session: Session, sample_users: list[User]):
        """Test that fetch_data returns users from database."""
        exporter = InscriptionsExporter()
        exporter.do_start_date()  # Initialize start_date

        data = exporter.fetch_data()

        assert isinstance(data, list)
        # Should have at least the test users created recently
        assert len(data) >= 3


class TestModificationsExporter:
    """Test ModificationsExporter class."""

    def test_exporter_initializes(self):
        """Test that ModificationsExporter can be instantiated."""
        exporter = ModificationsExporter()
        assert exporter is not None
        assert exporter.sheet_name == "Modifications"

    def test_exporter_inherits_from_inscriptions(self):
        """Test that ModificationsExporter inherits from InscriptionsExporter."""
        exporter = ModificationsExporter()
        assert isinstance(exporter, InscriptionsExporter)
        assert isinstance(exporter, BaseExporter)

    def test_exporter_has_columns_defined(self):
        """Test that ModificationsExporter has column definitions."""
        exporter = ModificationsExporter()
        assert len(exporter.columns) > 0
        assert isinstance(exporter.columns, list)
        # ModificationsExporter should have specific columns
        assert "validation_status" in exporter.columns
        assert "modified_at" not in exporter.columns  # Uses submited_at instead

    def test_exporter_filename_format(self):
        """Test filename format after initializing dates."""
        exporter = ModificationsExporter()
        exporter.do_start_date()  # Initialize dates without running full export
        assert "modification" in exporter.filename.lower()
        assert exporter.filename.endswith(".ods")

    def test_exporter_title_format(self):
        """Test title format after initializing dates."""
        exporter = ModificationsExporter()
        exporter.do_start_date()  # Initialize dates without running full export
        assert len(exporter.title) > 0
        assert isinstance(exporter.title, str)
        assert "modification" in exporter.title.lower()

    def test_fetch_data(self, db_session: Session, sample_users: list[User]):
        """Test that fetch_data filters modified users correctly."""
        exporter = ModificationsExporter()
        exporter.do_start_date()  # Initialize start_date

        data = exporter.fetch_data()

        # Result should be a list (might be empty if no modified users)
        assert isinstance(data, list)


class TestUsersExporter:
    """Test UsersExporter class."""

    def test_exporter_initializes(self):
        """Test that UsersExporter can be instantiated."""
        exporter = UsersExporter()
        assert exporter is not None
        assert exporter.sheet_name == "Utilisateurs"

    def test_exporter_inherits_from_inscriptions(self):
        """Test that UsersExporter inherits from InscriptionsExporter."""
        exporter = UsersExporter()
        assert isinstance(exporter, InscriptionsExporter)
        assert isinstance(exporter, BaseExporter)

    def test_exporter_has_columns_defined(self):
        """Test that UsersExporter has column definitions."""
        exporter = UsersExporter()
        assert len(exporter.columns) > 0
        assert isinstance(exporter.columns, list)
        # UsersExporter should have more columns than InscriptionsExporter
        assert "last_login_at" in exporter.columns
        assert "login_count" in exporter.columns
        assert "karma" in exporter.columns

    def test_exporter_filename_format(self):
        """Test filename format after initializing dates."""
        exporter = UsersExporter()
        exporter.do_start_date()  # Initialize dates without running full export
        assert "utilisateur" in exporter.filename.lower()
        assert exporter.filename.endswith(".ods")

    def test_exporter_title_format(self):
        """Test title format after initializing dates."""
        exporter = UsersExporter()
        exporter.do_start_date()  # Initialize dates without running full export
        assert len(exporter.title) > 0
        assert isinstance(exporter.title, str)
        assert exporter.title == "Utilisateurs"

    def test_fetch_data(self, db_session: Session, sample_users: list[User]):
        """Test that fetch_data returns all active users."""
        exporter = UsersExporter()
        exporter.do_start_date()  # Initialize start_date

        data = exporter.fetch_data()

        assert isinstance(data, list)
        # Should have at least the test users
        assert len(data) >= 3


class TestOrganisationsExporter:
    """Test OrganisationsExporter class."""

    def test_exporter_creates_document(
        self, db_session: Session, sample_organisations: list[Organisation]
    ):
        """Test that OrganisationsExporter generates valid ODS document."""
        exporter = OrganisationsExporter()
        exporter.run()

        assert exporter.document is not None
        assert len(exporter.document) > 0
        # ODS files start with ZIP signature
        assert exporter.document[:4] == b"PK\x03\x04"

    def test_exporter_has_correct_filename(
        self, db_session: Session, sample_organisations: list[Organisation]
    ):
        """Test that OrganisationsExporter has correct filename format after run."""
        exporter = OrganisationsExporter()
        exporter.run()  # Initialize date fields
        assert "organisation" in exporter.filename.lower()
        assert exporter.filename.endswith(".ods")

    def test_exporter_title(
        self, db_session: Session, sample_organisations: list[Organisation]
    ):
        """Test that OrganisationsExporter has correct title after run."""
        exporter = OrganisationsExporter()
        exporter.run()  # Initialize date fields
        assert len(exporter.title) > 0
        assert isinstance(exporter.title, str)

    def test_fetch_data(
        self, db_session: Session, sample_organisations: list[Organisation]
    ):
        """Test that fetch_data returns organisations."""
        exporter = OrganisationsExporter()
        data = exporter.fetch_data()

        assert isinstance(data, list)
        assert len(data) >= 3  # At least the 3 we created
        assert all(isinstance(org, Organisation) for org in data)
