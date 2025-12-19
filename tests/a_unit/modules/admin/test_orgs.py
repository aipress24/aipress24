# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Unit tests for admin/pages/orgs.py - testing pure functionality only."""

from __future__ import annotations

from app.models.organisation import Organisation
from app.modules.admin.pages.orgs import AdminOrgsPage
from app.modules.admin.views._orgs import (
    OrgDataSource,
    OrgsTable,
)
from app.modules.admin.table import GenericOrgDataSource


class TestOrgsTable:
    """Test suite for OrgsTable - pure class testing."""

    def test_table_columns(self):
        """Test that OrgsTable has correct columns."""
        table = OrgsTable([])
        columns = list(table.compose())

        expected_columns = [
            {"name": "name", "label": "Nom", "width": 50},
            {"name": "type", "label": "type", "width": 20},
            {"name": "karma", "label": "Réputation", "width": 8},
        ]

        for i, col in enumerate(columns):
            assert col.name == expected_columns[i]["name"]
            assert col.label == expected_columns[i]["label"]
            assert col.width == expected_columns[i]["width"]

    def test_table_attributes(self):
        """Test OrgsTable attributes."""
        table = OrgsTable([])
        assert table.url_label == "Détail"
        assert not table.all_search


class TestOrgDataSource:
    """Test suite for OrgDataSource - testing with real database."""

    def test_org_datasource_inheritance(self):
        """Test that OrgDataSource inherits from GenericOrgDataSource."""
        ds = OrgDataSource()
        assert isinstance(ds, GenericOrgDataSource)

    def test_count_with_real_orgs(self, db_session):
        """Test count method with real database organizations."""
        # Create real organizations
        org1 = Organisation(name="Test Org 1")
        org2 = Organisation(name="Test Org 2")
        db_session.add_all([org1, org2])
        db_session.flush()

        ds = OrgDataSource()
        count = ds.count()

        # Should count the organizations
        assert count >= 2  # At least our 2 test orgs


class TestAdminOrgsPage:
    """Test suite for AdminOrgsPage - testing pure attributes."""

    def test_page_attributes(self):
        """Test AdminOrgsPage class attributes."""
        # These are class attributes that don't require instantiation
        assert AdminOrgsPage.name == "orgs"
        assert AdminOrgsPage.label == "Organisations"
        assert AdminOrgsPage.title == "Organisations"
        assert AdminOrgsPage.icon == "building"
        assert AdminOrgsPage.template == "admin/pages/generic_table.j2"

    def test_page_instantiation(self, db_session):
        """Test that AdminOrgsPage can be instantiated."""
        # This tests that the page can be created without errors
        page = AdminOrgsPage()
        assert page is not None
        assert hasattr(page, "context")
        assert hasattr(page, "hx_post")
