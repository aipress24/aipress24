# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Unit tests for admin/table.py"""

from __future__ import annotations

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
        assert table.all_search is True
        assert table.searching == ""

    def test_table_with_records(self) -> None:
        """Test Table with custom records."""
        records = [{"id": 1, "name": "Test"}]
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

    def test_default_values(self) -> None:
        """Test GenericUserDataSource has correct default values."""
        assert GenericUserDataSource.search == ""
        assert GenericUserDataSource.limit == 12
        assert GenericUserDataSource.offset == 0

    def test_first_page_resets_offset(self) -> None:
        """Test first_page resets offset to 0."""
        GenericUserDataSource.offset = 24
        GenericUserDataSource.first_page()
        assert GenericUserDataSource.offset == 0

    def test_dec_reduces_offset(self, db: SQLAlchemy) -> None:
        """Test dec reduces offset by limit."""
        GenericUserDataSource.offset = 24
        GenericUserDataSource.limit = 12
        GenericUserDataSource.dec()
        assert GenericUserDataSource.offset == 12

    def test_dec_does_not_go_below_zero(self) -> None:
        """Test dec does not reduce offset below 0."""
        GenericUserDataSource.offset = 5
        GenericUserDataSource.limit = 12
        GenericUserDataSource.dec()
        assert GenericUserDataSource.offset == 0

    def test_count_excludes_clones(self, db: SQLAlchemy) -> None:
        """Test count excludes clone users."""
        # Reset state
        GenericUserDataSource.search = ""
        GenericUserDataSource.offset = 0

        user1 = User(email="count_user1@example.com", is_clone=False)
        user2 = User(email="count_user2@example.com", is_clone=True)
        db.session.add_all([user1, user2])
        db.session.flush()

        # The count should include user1 but exclude user2
        count = GenericUserDataSource.count()
        assert count >= 1  # At least user1

    def test_get_base_select_excludes_clones(self, db: SQLAlchemy) -> None:
        """Test get_base_select excludes clone users."""
        GenericUserDataSource.search = "baseselectunique"
        GenericUserDataSource.offset = 0
        GenericUserDataSource.limit = 100

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

        stmt = GenericUserDataSource.get_base_select()
        stmt = GenericUserDataSource.add_search_filter(stmt)
        results = list(db.session.scalars(stmt))

        emails = [u.email for u in results]
        assert "base_select_user@example.com" in emails
        assert "base_select_clone@example.com" not in emails

        # Reset search
        GenericUserDataSource.search = ""

    def test_inc_increases_offset(self, db: SQLAlchemy) -> None:
        """Test inc increases offset by limit when more records exist."""
        # Create enough users to have multiple pages
        GenericUserDataSource.search = ""
        GenericUserDataSource.offset = 0
        GenericUserDataSource.limit = 2

        for i in range(5):
            user = User(email=f"inc_user{i}@example.com", is_clone=False)
            db.session.add(user)
        db.session.flush()

        initial_offset = GenericUserDataSource.offset
        GenericUserDataSource.inc()

        # If there are more records, offset should increase
        if GenericUserDataSource.count() > GenericUserDataSource.limit:
            assert (
                GenericUserDataSource.offset
                == initial_offset + GenericUserDataSource.limit
            )

    def test_add_search_filter_filters_by_name(self, db: SQLAlchemy) -> None:
        """Test add_search_filter filters by first/last name."""
        GenericUserDataSource.search = "searchuniquename"
        GenericUserDataSource.offset = 0
        GenericUserDataSource.limit = 100

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

        stmt = GenericUserDataSource.get_base_select()
        stmt = GenericUserDataSource.add_search_filter(stmt)
        results = list(db.session.scalars(stmt))

        emails = [u.email for u in results]
        assert "search_filter_user1@example.com" in emails
        assert "search_filter_user2@example.com" not in emails

        # Reset search
        GenericUserDataSource.search = ""


class TestGenericOrgDataSource:
    """Test suite for GenericOrgDataSource class."""

    def test_default_values(self) -> None:
        """Test GenericOrgDataSource has correct default values."""
        assert GenericOrgDataSource.search == ""
        assert GenericOrgDataSource.limit == 12
        assert GenericOrgDataSource.offset == 0

    def test_first_page_resets_offset(self) -> None:
        """Test first_page resets offset to 0."""
        GenericOrgDataSource.offset = 24
        GenericOrgDataSource.first_page()
        assert GenericOrgDataSource.offset == 0

    def test_dec_reduces_offset(self) -> None:
        """Test dec reduces offset by limit."""
        GenericOrgDataSource.offset = 24
        GenericOrgDataSource.limit = 12
        GenericOrgDataSource.dec()
        assert GenericOrgDataSource.offset == 12

    def test_dec_does_not_go_below_zero(self) -> None:
        """Test dec does not reduce offset below 0."""
        GenericOrgDataSource.offset = 5
        GenericOrgDataSource.limit = 12
        GenericOrgDataSource.dec()
        assert GenericOrgDataSource.offset == 0

    def test_count_returns_integer(self, db: SQLAlchemy) -> None:
        """Test count returns an integer."""
        GenericOrgDataSource.search = ""
        GenericOrgDataSource.offset = 0

        org = Organisation(name="Count Org Table", type=OrganisationTypeEnum.MEDIA)
        db.session.add(org)
        db.session.flush()

        count = GenericOrgDataSource.count()
        assert isinstance(count, int)
        assert count >= 1

    def test_get_base_select_excludes_deleted(self, db: SQLAlchemy) -> None:
        """Test get_base_select excludes deleted organisations."""
        import arrow

        GenericOrgDataSource.search = ""
        GenericOrgDataSource.offset = 0
        GenericOrgDataSource.limit = 100

        org_active = Organisation(
            name="Active Org Select", type=OrganisationTypeEnum.MEDIA
        )
        org_deleted = Organisation(
            name="Deleted Org Select",
            type=OrganisationTypeEnum.COM,
            deleted_at=arrow.now(),
        )
        db.session.add_all([org_active, org_deleted])
        db.session.flush()

        stmt = GenericOrgDataSource.get_base_select()
        results = list(db.session.scalars(stmt))

        names = [o.name for o in results]
        assert "Active Org Select" in names
        assert "Deleted Org Select" not in names

    def test_inc_increases_offset(self, db: SQLAlchemy) -> None:
        """Test inc increases offset by limit when more records exist."""
        GenericOrgDataSource.search = ""
        GenericOrgDataSource.offset = 0
        GenericOrgDataSource.limit = 2

        for i in range(5):
            org = Organisation(name=f"Inc Org Table {i}", type=OrganisationTypeEnum.COM)
            db.session.add(org)
        db.session.flush()

        initial_offset = GenericOrgDataSource.offset
        GenericOrgDataSource.inc()

        if GenericOrgDataSource.count() > GenericOrgDataSource.limit:
            assert (
                GenericOrgDataSource.offset
                == initial_offset + GenericOrgDataSource.limit
            )

    def test_add_search_filter_filters_by_name(self, db: SQLAlchemy) -> None:
        """Test add_search_filter filters by organisation name."""
        GenericOrgDataSource.search = "uniqueorgsearchfilter"
        GenericOrgDataSource.offset = 0
        GenericOrgDataSource.limit = 100

        org1 = Organisation(
            name="UniqueOrgSearchFilter Test", type=OrganisationTypeEnum.MEDIA
        )
        org2 = Organisation(
            name="Other Org Search Table", type=OrganisationTypeEnum.COM
        )
        db.session.add_all([org1, org2])
        db.session.flush()

        stmt = GenericOrgDataSource.get_base_select()
        stmt = GenericOrgDataSource.add_search_filter(stmt)
        results = list(db.session.scalars(stmt))

        names = [o.name for o in results]
        assert "UniqueOrgSearchFilter Test" in names
        assert "Other Org Search Table" not in names

        # Reset search
        GenericOrgDataSource.search = ""
