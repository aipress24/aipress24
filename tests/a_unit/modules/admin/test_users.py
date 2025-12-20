# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Unit tests for admin/pages/users.py - UsersTable and UserDataSource."""

from __future__ import annotations

import arrow
from flask import Flask
from flask_sqlalchemy import SQLAlchemy

from app.models.auth import User
from app.modules.admin.views._users import (
    TABLE_COLUMNS,
    UserDataSource,
    UsersTable,
)


class TestUsersTable:
    """Test UsersTable class."""

    def test_table_columns(self):
        """Test UsersTable yields correct columns."""
        table = UsersTable([])
        columns = list(table.compose())

        assert len(columns) == len(TABLE_COLUMNS)
        for i, col in enumerate(columns):
            assert col.name == TABLE_COLUMNS[i]["name"]
            assert col.label == TABLE_COLUMNS[i]["label"]

    def test_table_url_label(self):
        """Test UsersTable has correct url_label."""
        table = UsersTable([])
        assert table.url_label == "Détail"

    def test_table_all_search_disabled(self):
        """Test UsersTable has all_search disabled."""
        table = UsersTable([])
        assert table.all_search is False


class TestUserDataSource:
    """Test UserDataSource class."""

    def test_count_excludes_inactive(self, app: Flask, db: SQLAlchemy) -> None:
        """Test count excludes inactive users."""
        active_user = User(
            email="active_user_ds@example.com",
            active=True,
            is_clone=False,
        )
        inactive_user = User(
            email="inactive_user_ds@example.com",
            active=False,
            is_clone=False,
        )
        db.session.add_all([active_user, inactive_user])
        db.session.flush()

        with app.test_request_context("/"):
            ds = UserDataSource()
            # Count should include active user but not inactive
            count_before = ds.count()

            # Add another active user
            another_active = User(
                email="another_active_ds@example.com",
                active=True,
                is_clone=False,
            )
            db.session.add(another_active)
            db.session.flush()

            count_after = ds.count()
            assert count_after == count_before + 1

    def test_count_excludes_deleted(self, app: Flask, db: SQLAlchemy) -> None:
        """Test count excludes deleted users."""
        with app.test_request_context("/"):
            # Get initial count
            ds = UserDataSource()
            initial_count = ds.count()

            # Add normal user (should be counted)
            normal_user = User(
                email="normal_user_ds@example.com",
                active=True,
                is_clone=False,
            )
            db.session.add(normal_user)
            db.session.flush()

            ds = UserDataSource()
            count_with_normal = ds.count()
            assert count_with_normal == initial_count + 1

            # Add deleted user (should NOT be counted)
            deleted_user = User(
                email="deleted_user_ds@example.com",
                active=True,
                is_clone=False,
                deleted_at=arrow.now().datetime,
            )
            db.session.add(deleted_user)
            db.session.flush()

            ds = UserDataSource()
            count_with_deleted = ds.count()
            # Count should remain the same (deleted user excluded)
            assert count_with_deleted == count_with_normal

    def test_count_excludes_clones(self, app: Flask, db: SQLAlchemy) -> None:
        """Test count excludes clone users."""
        with app.test_request_context("/"):
            # Get initial count
            ds = UserDataSource()
            initial_count = ds.count()

            # Add real user (should be counted)
            real_user = User(
                email="real_user_ds@example.com",
                active=True,
                is_clone=False,
            )
            db.session.add(real_user)
            db.session.flush()

            ds = UserDataSource()
            count_with_real = ds.count()
            assert count_with_real == initial_count + 1

            # Add clone user (should NOT be counted)
            clone_user = User(
                email="clone_user_ds@example.com",
                active=True,
                is_clone=True,
            )
            db.session.add(clone_user)
            db.session.flush()

            ds = UserDataSource()
            count_with_clone = ds.count()
            # Count should remain the same (clone excluded)
            assert count_with_clone == count_with_real

    def test_get_base_select_returns_select(self, app: Flask, db: SQLAlchemy) -> None:
        """Test get_base_select returns proper select statement."""
        from sqlalchemy import Select

        with app.test_request_context("/"):
            ds = UserDataSource()
            stmt = ds.get_base_select()

            assert isinstance(stmt, Select)
            assert str(stmt).upper().startswith("SELECT")


class TestTableColumnsConfiguration:
    """Test TABLE_COLUMNS configuration."""

    def test_columns_count(self):
        """Test TABLE_COLUMNS has expected number of columns."""
        assert len(TABLE_COLUMNS) == 6

    def test_columns_have_required_keys(self):
        """Test each column has required keys."""
        for col in TABLE_COLUMNS:
            assert "name" in col
            assert "label" in col
            assert "width" in col

    def test_column_names(self):
        """Test TABLE_COLUMNS has expected column names."""
        names = [col["name"] for col in TABLE_COLUMNS]
        expected = [
            "email",
            "karma",
            "name",
            "job_title",
            "organisation_name",
            "status",
        ]
        assert names == expected
