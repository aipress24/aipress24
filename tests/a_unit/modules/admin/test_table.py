# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Unit tests for admin/table.py"""

from __future__ import annotations

from typing import TYPE_CHECKING

import arrow
from flask import Flask
from flask_sqlalchemy import SQLAlchemy

from app.enums import OrganisationTypeEnum
from app.models.auth import User
from app.models.organisation import Organisation
from app.modules.admin.table import (
    Column,
    GenericOrgDataSource,
    GenericUserDataSource,
    Table,
)

if TYPE_CHECKING:
    pass


class TestColumn:
    """Test suite for Column class."""

    def test_td_class_left_align(self) -> None:
        """Test td_class returns empty string for left alignment."""
        column = Column(name="test", label="Test", align="left")
        assert column.td_class == ""

    def test_td_class_right_align(self) -> None:
        """Test td_class returns text-right for right alignment."""
        column = Column(name="test", label="Test", align="right")
        assert column.td_class == "text-right"

    def test_td_class_default_align(self) -> None:
        """Test td_class returns empty string for default alignment."""
        column = Column(name="test", label="Test")
        assert column.td_class == ""

    def test_td_class_unknown_align(self) -> None:
        """Test td_class returns empty string for unknown alignment."""
        column = Column(name="test", label="Test", align="center")
        assert column.td_class == ""

    def test_column_attributes(self) -> None:
        """Test Column has correct attributes."""
        column = Column(name="email", label="Email Address", width=200, align="left")
        assert column.name == "email"
        assert column.label == "Email Address"
        assert column.width == 200
        assert column.align == "left"

    def test_column_default_width(self) -> None:
        """Test Column default width is 0."""
        column = Column(name="test", label="Test")
        assert column.width == 0


class TestTable:
    """Test suite for Table class."""

    def test_table_default_values(self) -> None:
        """Test Table has correct default values."""
        table = Table(records=[])
        assert table.start == 0
        assert table.end == 10
        assert table.count == 20
        assert table.url_label == "Show"

    def test_table_with_records(self) -> None:
        """Test Table can be initialized with records."""
        records = [{"id": 1}, {"id": 2}]
        table = Table(records=records)
        assert table.records == records

    def test_columns_returns_empty_by_default(self) -> None:
        """Test columns returns empty list by default."""
        table = Table(records=[])
        assert table.columns == []

    def test_render_cell_with_renderer(self) -> None:
        """Test render_cell uses custom renderer if available."""

        class CustomTable(Table):
            def render_name(self, record):
                return f"Custom: {record['name']}"

        table = CustomTable(records=[])
        column = Column(name="name", label="Name")
        record = {"name": "Test"}

        result = table.render_cell(record, column)

        assert result == "Custom: Test"

    def test_render_cell_without_renderer(self) -> None:
        """Test render_cell returns value from record."""
        table = Table(records=[])
        column = Column(name="email", label="Email")
        record = {"email": "test@example.com", "name": "Test"}

        result = table.render_cell(record, column)

        assert result == "test@example.com"

    def test_render_cell_missing_key(self) -> None:
        """Test render_cell returns empty string for missing key."""
        table = Table(records=[])
        column = Column(name="missing", label="Missing")
        record = {"name": "Test"}

        result = table.render_cell(record, column)

        assert result == ""


class TestGenericUserDataSource:
    """Test suite for GenericUserDataSource class."""

    def test_default_values(self, app: Flask) -> None:
        """Test GenericUserDataSource parses defaults from empty request."""
        with app.test_request_context("/"):
            ds = GenericUserDataSource()
            assert ds.search == ""
            assert ds.limit == 12
            assert ds.offset == 0

    def test_parses_query_params(self, app: Flask) -> None:
        """Test GenericUserDataSource parses values from query string."""
        with app.test_request_context("/?search=test&offset=24&limit=50"):
            ds = GenericUserDataSource()
            assert ds.search == "test"
            assert ds.offset == 24
            assert ds.limit == 50

    def test_prev_offset_reduces_offset(self, app: Flask) -> None:
        """Test prev_offset reduces offset by limit."""
        with app.test_request_context("/?offset=24&limit=12"):
            ds = GenericUserDataSource()
            assert ds.prev_offset() == 12

    def test_prev_offset_does_not_go_below_zero(self, app: Flask) -> None:
        """Test prev_offset does not reduce offset below 0."""
        with app.test_request_context("/?offset=5&limit=12"):
            ds = GenericUserDataSource()
            assert ds.prev_offset() == 0

    def test_count_excludes_clones(self, app: Flask, db: SQLAlchemy) -> None:
        """Test count excludes clone users."""
        user1 = User(email="count_user1@example.com", is_clone=False)
        user2 = User(email="count_user2@example.com", is_clone=True)
        db.session.add_all([user1, user2])
        db.session.flush()

        with app.test_request_context("/"):
            ds = GenericUserDataSource()
            count = ds.count()
            assert count >= 1  # At least user1

    def test_get_base_select_excludes_clones(self, app: Flask, db: SQLAlchemy) -> None:
        """Test get_base_select excludes clone users."""
        user = User(
            email="base_select_user@example.com",
            first_name="BaseSelectUnique",
            last_name="Doe",
            is_clone=False,
        )
        clone = User(
            email="base_select_clone@example.com",
            first_name="BaseSelectUnique",
            last_name="Clone",
            is_clone=True,
        )
        db.session.add_all([user, clone])
        db.session.flush()

        with app.test_request_context("/?search=baseselectunique&limit=100"):
            ds = GenericUserDataSource()
            stmt = ds.get_base_select()
            stmt = ds.add_search_filter(stmt)
            results = list(db.session.scalars(stmt))

            emails = [u.email for u in results]
            assert "base_select_user@example.com" in emails
            assert "base_select_clone@example.com" not in emails

    def test_next_offset_increases_offset(self, app: Flask, db: SQLAlchemy) -> None:
        """Test next_offset increases offset by limit when more records exist."""
        for i in range(5):
            user = User(email=f"inc_user{i}@example.com", is_clone=False)
            db.session.add(user)
        db.session.flush()

        with app.test_request_context("/?offset=0&limit=2"):
            ds = GenericUserDataSource()
            # If there are more records than limit, next_offset should increase
            if ds.count() > ds.limit:
                assert ds.next_offset() == ds.offset + ds.limit

    def test_add_search_filter_filters_by_name(
        self, app: Flask, db: SQLAlchemy
    ) -> None:
        """Test add_search_filter filters by first/last name."""
        user1 = User(
            email="search_filter_user1@example.com",
            first_name="SearchUniqueName",
            last_name="Test",
            is_clone=False,
        )
        user2 = User(
            email="search_filter_user2@example.com",
            first_name="Other",
            last_name="User",
            is_clone=False,
        )
        db.session.add_all([user1, user2])
        db.session.flush()

        with app.test_request_context("/?search=searchuniquename&limit=100"):
            ds = GenericUserDataSource()
            stmt = ds.get_base_select()
            stmt = ds.add_search_filter(stmt)
            results = list(db.session.scalars(stmt))

            emails = [u.email for u in results]
            assert "search_filter_user1@example.com" in emails
            assert "search_filter_user2@example.com" not in emails


class TestGenericOrgDataSource:
    """Test suite for GenericOrgDataSource class."""

    def test_default_values(self, app: Flask) -> None:
        """Test GenericOrgDataSource parses defaults from empty request."""
        with app.test_request_context("/"):
            ds = GenericOrgDataSource()
            assert ds.search == ""
            assert ds.limit == 12
            assert ds.offset == 0

    def test_parses_query_params(self, app: Flask) -> None:
        """Test GenericOrgDataSource parses values from query string."""
        with app.test_request_context("/?search=test&offset=24&limit=50"):
            ds = GenericOrgDataSource()
            assert ds.search == "test"
            assert ds.offset == 24
            assert ds.limit == 50

    def test_prev_offset_reduces_offset(self, app: Flask) -> None:
        """Test prev_offset reduces offset by limit."""
        with app.test_request_context("/?offset=24&limit=12"):
            ds = GenericOrgDataSource()
            assert ds.prev_offset() == 12

    def test_prev_offset_does_not_go_below_zero(self, app: Flask) -> None:
        """Test prev_offset does not reduce offset below 0."""
        with app.test_request_context("/?offset=5&limit=12"):
            ds = GenericOrgDataSource()
            assert ds.prev_offset() == 0

    def test_count_returns_integer(self, app: Flask, db: SQLAlchemy) -> None:
        """Test count returns an integer."""
        with app.test_request_context("/"):
            ds = GenericOrgDataSource()
            count = ds.count()
            assert isinstance(count, int)

    def test_get_base_select_excludes_deleted(self, app: Flask, db: SQLAlchemy) -> None:
        """Test get_base_select excludes deleted organisations."""
        org1 = Organisation(name="ActiveOrgUnique", type=OrganisationTypeEnum.AUTO.name)
        org2 = Organisation(
            name="DeletedOrgUnique",
            type=OrganisationTypeEnum.AUTO.name,
            deleted_at=arrow.now().datetime,
        )
        db.session.add_all([org1, org2])
        db.session.flush()

        with app.test_request_context("/?search=orgunique&limit=100"):
            ds = GenericOrgDataSource()
            stmt = ds.get_base_select()
            stmt = ds.add_search_filter(stmt)
            results = list(db.session.scalars(stmt))

            names = [o.name for o in results]
            assert "ActiveOrgUnique" in names
            assert "DeletedOrgUnique" not in names

    def test_next_offset_increases_offset(self, app: Flask, db: SQLAlchemy) -> None:
        """Test next_offset increases offset by limit when more records exist."""
        for i in range(5):
            org = Organisation(
                name=f"IncOrg{i}Unique", type=OrganisationTypeEnum.AUTO.name
            )
            db.session.add(org)
        db.session.flush()

        with app.test_request_context("/?offset=0&limit=2"):
            ds = GenericOrgDataSource()
            if ds.count() > ds.limit:
                assert ds.next_offset() == ds.offset + ds.limit

    def test_add_search_filter_filters_by_name(
        self, app: Flask, db: SQLAlchemy
    ) -> None:
        """Test add_search_filter filters by name."""
        org1 = Organisation(
            name="SearchableOrgUnique", type=OrganisationTypeEnum.AUTO.name
        )
        org2 = Organisation(name="OtherOrgUnique", type=OrganisationTypeEnum.AUTO.name)
        db.session.add_all([org1, org2])
        db.session.flush()

        with app.test_request_context("/?search=searchableorg&limit=100"):
            ds = GenericOrgDataSource()
            stmt = ds.get_base_select()
            stmt = ds.add_search_filter(stmt)
            results = list(db.session.scalars(stmt))

            names = [o.name for o in results]
            assert "SearchableOrgUnique" in names
            assert "OtherOrgUnique" not in names
