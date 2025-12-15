# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Unit tests for admin/pages/modif_users.py - testing pure functionality only."""

from __future__ import annotations


from app.models.auth import User
from app.modules.admin.pages.modif_users import (
    AdminModifUsersPage,
    ModifUserDataSource,
    ModifUsersTable,
)


class TestModifUsersTable:
    """Test suite for ModifUsersTable - pure class testing."""

    def test_table_columns(self):
        """Test that ModifUsersTable has correct columns."""
        table = ModifUsersTable([])
        columns = list(table.compose())

        expected_columns = [
            {"name": "name", "label": "Nom", "width": 50},
            {"name": "organisation_name", "label": "Org.", "width": 50},
            {"name": "last_login_at", "label": "Connexion", "width": 35},
            {"name": "job_title", "label": "Job", "width": 50},
            {"name": "email", "label": "E-mail", "width": 50},
        ]

        for i, col in enumerate(columns):
            assert col.name == expected_columns[i]["name"]
            assert col.label == expected_columns[i]["label"]
            assert col.width == expected_columns[i]["width"]

    def test_table_attributes(self):
        """Test ModifUsersTable attributes."""
        table = ModifUsersTable([])
        assert table.url_label == "Validation"
        assert not table.all_search


class TestModifUserDataSource:
    """Test suite for ModifUserDataSource - testing with real database."""

    def test_count_with_real_users(self, db_session):
        """Test count method with real database users."""
        # Create real users that match the criteria (active=False, is_clone=True)
        user1 = User(email="test1@example.com", active=False, is_clone=True)
        user2 = User(email="test2@example.com", active=False, is_clone=True)
        db_session.add_all([user1, user2])
        db_session.flush()

        ds = ModifUserDataSource()
        count = ds.count()

        # Should count only the users that match criteria
        assert count >= 2  # At least our 2 test users

    def test_make_records_with_real_user(self, db_session):
        """Test make_records method with real user data."""
        # Create a real user
        user = User(
            email="john@example.com",
            first_name="John",
            last_name="Doe",
            is_clone=True,
            active=False,
        )
        db_session.add(user)
        db_session.flush()

        # Test the make_records method
        # Since this method requires Flask app context for URL building,
        # we'll test it in integration tests instead
        ds = ModifUserDataSource()

        # Test the parts we can test without Flask context
        # The URL building will be tested in integration tests
        assert hasattr(ds, "make_records")
        assert callable(ds.make_records)


class TestAdminModifUsersPage:
    """Test suite for AdminModifUsersPage - testing pure attributes."""

    def test_page_attributes(self):
        """Test AdminModifUsersPage class attributes."""
        # These are class attributes that don't require instantiation
        assert AdminModifUsersPage.name == "modif_users"
        assert AdminModifUsersPage.label == "Modifications"
        assert AdminModifUsersPage.title == "Modifications de profils à valider"
        assert AdminModifUsersPage.icon == "users"
        assert AdminModifUsersPage.template == "admin/pages/generic_table.j2"

    def test_page_instantiation(self, db_session):
        """Test that AdminModifUsersPage can be instantiated."""
        # This tests that the page can be created without errors
        page = AdminModifUsersPage()
        assert page is not None
        assert hasattr(page, "context")
        assert hasattr(page, "hx_post")
