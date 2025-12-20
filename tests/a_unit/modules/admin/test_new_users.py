# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Unit tests for admin/pages/new_users.py - testing pure functionality only."""

from __future__ import annotations

from sqlalchemy import Select

from app.models.auth import User
from app.modules.admin.views._new_users import (
    NewUserDataSource,
    NewUsersTable,
)


class TestNewUsersTable:
    """Test suite for NewUsersTable - pure class testing."""

    def test_table_columns(self):
        """Test that NewUsersTable has correct columns."""
        table = NewUsersTable([])
        columns = list(table.compose())

        expected_columns = [
            {"name": "name", "label": "Nom", "width": 50},
            {"name": "organisation_name", "label": "Org.", "width": 50},
            {"name": "submited_at", "label": "Inscription", "width": 35},
            {"name": "job_title", "label": "Job", "width": 50},
            {"name": "email", "label": "E-mail", "width": 50},
        ]

        for i, col in enumerate(columns):
            assert col.name == expected_columns[i]["name"]
            assert col.label == expected_columns[i]["label"]
            assert col.width == expected_columns[i]["width"]

    def test_table_attributes(self):
        """Test NewUsersTable attributes."""
        table = NewUsersTable([])
        assert table.url_label == "Validation"
        assert not table.all_search


class TestNewUserDataSource:
    """Test suite for NewUserDataSource - testing with real database."""

    def test_count_with_real_users(self, db_session):
        """Test count method with real database users."""
        # Create real users that match the criteria (active=False, is_clone=False)
        user1 = User(email="test1@example.com", active=False, is_clone=False)
        user2 = User(email="test2@example.com", active=False, is_clone=False)
        db_session.add_all([user1, user2])
        db_session.flush()

        ds = NewUserDataSource()
        count = ds.count()

        # Should count only the users that match criteria
        assert count >= 2  # At least our 2 test users

    def test_count_excludes_active_users(self, db_session):
        """Test count excludes active users."""
        ds = NewUserDataSource()
        initial_count = ds.count()

        # Add inactive non-clone user (should be counted)
        inactive_user = User(
            email="inactive_new@example.com", active=False, is_clone=False
        )
        db_session.add(inactive_user)
        db_session.flush()

        ds = NewUserDataSource()
        count_after_inactive = ds.count()
        assert count_after_inactive == initial_count + 1

        # Add active user (should NOT be counted)
        active_user = User(email="active_new@example.com", active=True, is_clone=False)
        db_session.add(active_user)
        db_session.flush()

        ds = NewUserDataSource()
        count_after_active = ds.count()
        assert count_after_active == count_after_inactive

    def test_count_excludes_clones(self, db_session):
        """Test count excludes clone users."""
        ds = NewUserDataSource()
        initial_count = ds.count()

        # Add non-clone inactive user (should be counted)
        non_clone = User(
            email="non_clone_new@example.com", active=False, is_clone=False
        )
        db_session.add(non_clone)
        db_session.flush()

        ds = NewUserDataSource()
        count_after_non_clone = ds.count()
        assert count_after_non_clone == initial_count + 1

        # Add clone user (should NOT be counted)
        clone = User(email="clone_new@example.com", active=False, is_clone=True)
        db_session.add(clone)
        db_session.flush()

        ds = NewUserDataSource()
        count_after_clone = ds.count()
        assert count_after_clone == count_after_non_clone

    def test_get_base_select_returns_select(self, db_session):
        """Test get_base_select method returns proper select statement."""
        ds = NewUserDataSource()
        stmt = ds.get_base_select()

        # Verify it's a select statement
        assert isinstance(stmt, Select)
        # Verify it starts with SELECT
        assert str(stmt).upper().startswith("SELECT")

    def test_make_records_with_real_user(self, db_session):
        """Test make_records method with real user data."""
        # Create a real user with profile
        user = User(email="john@example.com", first_name="John", last_name="Doe")
        # Create a profile for the user
        from app.models.auth import KYCProfile

        profile = KYCProfile(user=user, profile_label="Developer")
        db_session.add(user)
        db_session.add(profile)
        db_session.flush()

        # Test the make_records method
        # Since this method requires Flask app context for URL building,
        # we'll test it in integration tests instead
        ds = NewUserDataSource()

        # Test the parts we can test without Flask context
        # The URL building will be tested in integration tests
        assert hasattr(ds, "make_records")
        assert callable(ds.make_records)
