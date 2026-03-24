# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""E2E tests for ontology blueprint."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from flask import session, url_for
from flask_security import login_user

from app.blueprints.ontology.forms import CreateTaxonomyForm, TaxonomyEntryForm
from app.enums import RoleEnum
from app.models.auth import Role, User
from app.services.taxonomies import TaxonomyEntry

if TYPE_CHECKING:
    from flask import Flask
    from flask.testing import FlaskClient
    from sqlalchemy.orm import Session


def make_admin_client(app: Flask, user: User) -> FlaskClient:
    """Create an authenticated Flask test client for the given admin user."""
    client = app.test_client()
    with app.test_request_context():
        login_user(user)
        with client.session_transaction() as sess:
            for key, value in session.items():
                sess[key] = value
    return client


@pytest.fixture
def admin_role(db_session: Session) -> Role:
    """Create admin role."""
    role = Role(name=RoleEnum.ADMIN.name, description="Administrator")
    db_session.add(role)
    db_session.commit()
    return role


@pytest.fixture
def admin_user(db_session: Session, admin_role: Role) -> User:
    """Create admin user."""
    user = User(
        email="ontology_admin@example.com",
        first_name="Ontology",
        last_name="Admin",
        active=True,
    )
    user.roles.append(admin_role)
    db_session.add(user)
    db_session.commit()
    return user


@pytest.fixture
def admin_client(app: Flask, admin_user: User) -> FlaskClient:
    """Create test client logged in as admin."""
    return make_admin_client(app, admin_user)


@pytest.fixture
def taxonomy_entry(db_session: Session) -> TaxonomyEntry:
    """Create a test taxonomy entry."""
    entry = TaxonomyEntry(
        taxonomy_name="test_taxonomy",
        name="Test Entry",
        category="test_category",
        value="test_value",
        seq=1,
    )
    db_session.add(entry)
    db_session.commit()
    return entry


@pytest.fixture
def multiple_entries(db_session: Session) -> list[TaxonomyEntry]:
    """Create multiple taxonomy entries."""
    entries = []
    for i in range(3):
        entry = TaxonomyEntry(
            taxonomy_name="multi_taxonomy",
            name=f"Entry {i}",
            category=f"category_{i}",
            value=f"value_{i}",
            seq=i,
        )
        db_session.add(entry)
        entries.append(entry)
    db_session.commit()
    return entries


class TestContextProcessor:
    """Test ontology blueprint context processor."""

    def test_context_processor_basic_breadcrumbs(
        self, admin_client: FlaskClient, app: Flask
    ):
        """Test context processor returns basic breadcrumbs via rendered page."""
        with app.test_request_context():
            url = url_for("ontology.list_entries")
        response = admin_client.get(url)
        assert response.status_code == 200
        # Verify breadcrumbs are in the rendered HTML
        assert b"Admin" in response.data
        assert b"Ontology" in response.data

    def test_context_processor_with_taxonomy_name(
        self, admin_client: FlaskClient, app: Flask, taxonomy_entry: TaxonomyEntry
    ):
        """Test context processor adds taxonomy to breadcrumbs when present."""
        with app.test_request_context():
            url = url_for("ontology.list_entries", taxonomy_name="test_taxonomy")
        response = admin_client.get(url)
        assert response.status_code == 200
        assert b"test_taxonomy" in response.data


class TestTaxonomyEntryForm:
    """Test TaxonomyEntryForm validation."""

    def test_form_valid_data(self, app: Flask):
        """Test form accepts valid data."""
        with app.test_request_context():
            form = TaxonomyEntryForm(
                data={
                    "name": "Test Name",
                    "category": "Test Category",
                    "value": "test_value",
                    "seq": 5,
                }
            )
            assert form.validate()

    def test_form_missing_name(self, app: Flask):
        """Test form rejects missing name."""
        with app.test_request_context():
            form = TaxonomyEntryForm(
                data={
                    "name": "",
                    "value": "test_value",
                }
            )
            assert not form.validate()
            assert "name" in form.errors

    def test_form_missing_value(self, app: Flask):
        """Test form rejects missing value."""
        with app.test_request_context():
            form = TaxonomyEntryForm(
                data={
                    "name": "Test Name",
                    "value": "",
                }
            )
            assert not form.validate()
            assert "value" in form.errors

    def test_form_optional_category(self, app: Flask):
        """Test form accepts empty category."""
        with app.test_request_context():
            form = TaxonomyEntryForm(
                data={
                    "name": "Test Name",
                    "category": "",
                    "value": "test_value",
                }
            )
            assert form.validate()

    def test_form_optional_seq(self, app: Flask):
        """Test form accepts empty seq (defaults to 0)."""
        with app.test_request_context():
            form = TaxonomyEntryForm(
                data={
                    "name": "Test Name",
                    "value": "test_value",
                }
            )
            assert form.validate()


class TestCreateTaxonomyForm:
    """Test CreateTaxonomyForm validation."""

    def test_form_valid_name(self, app: Flask, db_session: Session):
        """Test form accepts valid new taxonomy name."""
        with app.test_request_context():
            form = CreateTaxonomyForm(data={"name": "new_taxonomy"})
            assert form.validate()

    def test_form_missing_name(self, app: Flask):
        """Test form rejects missing name."""
        with app.test_request_context():
            form = CreateTaxonomyForm(data={"name": ""})
            assert not form.validate()
            assert "name" in form.errors

    def test_form_duplicate_name(self, app: Flask, taxonomy_entry: TaxonomyEntry):
        """Test form rejects duplicate taxonomy name."""
        with app.test_request_context():
            form = CreateTaxonomyForm(data={"name": "test_taxonomy"})
            assert not form.validate()
            assert "name" in form.errors
            assert "already exists" in form.errors["name"][0]


class TestListEntriesRoute:
    """Test list_entries route."""

    def test_list_entries_no_taxonomy(self, admin_client: FlaskClient, app: Flask):
        """Test list entries page without taxonomy selected."""
        with app.test_request_context():
            url = url_for("ontology.list_entries")
        response = admin_client.get(url)
        assert response.status_code == 200

    def test_list_entries_with_taxonomy(
        self, admin_client: FlaskClient, app: Flask, taxonomy_entry: TaxonomyEntry
    ):
        """Test list entries page with taxonomy selected."""
        with app.test_request_context():
            url = url_for("ontology.list_entries", taxonomy_name="test_taxonomy")
        response = admin_client.get(url)
        assert response.status_code == 200
        assert b"Test Entry" in response.data

    def test_list_entries_shows_all_taxonomies(
        self,
        admin_client: FlaskClient,
        app: Flask,
        multiple_entries: list[TaxonomyEntry],
    ):
        """Test list entries shows all taxonomy names."""
        with app.test_request_context():
            url = url_for("ontology.list_entries")
        response = admin_client.get(url)
        assert response.status_code == 200

    def test_list_entries_unauthenticated_redirects(
        self, client: FlaskClient, app: Flask
    ):
        """Test list entries redirects unauthenticated users."""
        with app.test_request_context():
            url = url_for("ontology.list_entries")
        response = client.get(url)
        assert response.status_code == 302  # Redirect to login


class TestCreateTaxonomyRoute:
    """Test create_taxonomy route."""

    def test_create_taxonomy_get(self, admin_client: FlaskClient, app: Flask):
        """Test create taxonomy form page."""
        with app.test_request_context():
            url = url_for("ontology.create_taxonomy")
        response = admin_client.get(url)
        assert response.status_code == 200

    def test_create_taxonomy_post_success(
        self, admin_client: FlaskClient, app: Flask, db_session: Session
    ):
        """Test creating a new taxonomy."""
        with app.test_request_context():
            url = url_for("ontology.create_taxonomy")
        response = admin_client.post(url, data={"name": "brand_new_taxonomy"})
        assert response.status_code == 302  # Redirect on success

    def test_create_taxonomy_post_duplicate(
        self, admin_client: FlaskClient, app: Flask, taxonomy_entry: TaxonomyEntry
    ):
        """Test creating duplicate taxonomy fails."""
        with app.test_request_context():
            url = url_for("ontology.create_taxonomy")
        response = admin_client.post(url, data={"name": "test_taxonomy"})
        assert response.status_code == 200  # Returns form with errors


class TestCreateEntryRoute:
    """Test create entry route."""

    def test_create_entry_get(self, admin_client: FlaskClient, app: Flask):
        """Test create entry form page."""
        with app.test_request_context():
            url = url_for("ontology.create", taxonomy_name="test_taxonomy")
        response = admin_client.get(url)
        assert response.status_code == 200

    def test_create_entry_get_no_taxonomy(self, admin_client: FlaskClient, app: Flask):
        """Test create entry without taxonomy redirects."""
        with app.test_request_context():
            url = url_for("ontology.create")
        response = admin_client.get(url)
        assert response.status_code == 302  # Redirect

    def test_create_entry_post_success(
        self, admin_client: FlaskClient, app: Flask, db_session: Session
    ):
        """Test creating a new entry."""
        with app.test_request_context():
            url = url_for("ontology.create", taxonomy_name="new_taxonomy")
        response = admin_client.post(
            url,
            data={
                "name": "New Entry",
                "category": "cat",
                "value": "new_val",
                "seq": 0,
            },
        )
        assert response.status_code == 302  # Redirect on success


class TestEditEntryRoute:
    """Test edit entry route."""

    def test_edit_entry_get(
        self, admin_client: FlaskClient, app: Flask, taxonomy_entry: TaxonomyEntry
    ):
        """Test edit entry form page."""
        with app.test_request_context():
            url = url_for("ontology.edit", entry_id=taxonomy_entry.id)
        response = admin_client.get(url)
        assert response.status_code == 200
        assert b"Test Entry" in response.data

    def test_edit_entry_not_found(self, admin_client: FlaskClient, app: Flask):
        """Test edit non-existent entry redirects."""
        with app.test_request_context():
            url = url_for("ontology.edit", entry_id=99999)
        response = admin_client.get(url)
        assert response.status_code == 302  # Redirect

    def test_edit_entry_post_success(
        self,
        admin_client: FlaskClient,
        app: Flask,
        taxonomy_entry: TaxonomyEntry,
        db_session: Session,
    ):
        """Test updating an entry."""
        with app.test_request_context():
            url = url_for("ontology.edit", entry_id=taxonomy_entry.id)
        response = admin_client.post(
            url,
            data={
                "name": "Updated Entry",
                "category": "updated_cat",
                "value": "updated_val",
                "seq": 10,
            },
        )
        assert response.status_code == 302  # Redirect on success


class TestDeleteEntryRoute:
    """Test delete entry route."""

    def test_delete_entry_success(
        self,
        admin_client: FlaskClient,
        app: Flask,
        taxonomy_entry: TaxonomyEntry,
        db_session: Session,
    ):
        """Test deleting an entry."""
        with app.test_request_context():
            url = url_for("ontology.delete", entry_id=taxonomy_entry.id)
        response = admin_client.post(url)
        assert response.status_code == 302  # Redirect on success

    def test_delete_entry_not_found(self, admin_client: FlaskClient, app: Flask):
        """Test deleting non-existent entry."""
        with app.test_request_context():
            url = url_for("ontology.delete", entry_id=99999)
        response = admin_client.post(url)
        assert response.status_code == 302  # Redirect with flash


class TestExportRoute:
    """Test export route."""

    def test_export_ods_success(
        self, admin_client: FlaskClient, app: Flask, taxonomy_entry: TaxonomyEntry
    ):
        """Test exporting taxonomy to ODS."""
        with app.test_request_context():
            url = url_for("ontology.export_ods", taxonomy_name="test_taxonomy")
        response = admin_client.get(url)
        assert response.status_code == 200
        assert response.content_type == "application/vnd.oasis.opendocument.spreadsheet"

    def test_export_ods_not_found(self, admin_client: FlaskClient, app: Flask):
        """Test exporting non-existent taxonomy redirects."""
        with app.test_request_context():
            url = url_for("ontology.export_ods", taxonomy_name="nonexistent")
        response = admin_client.get(url)
        assert response.status_code == 302  # Redirect with flash
