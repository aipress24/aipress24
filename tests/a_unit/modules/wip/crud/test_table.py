# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Unit tests for WIP CRUD table classes."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock

from app.modules.wip.crud.cbvs._table import (
    BaseDataSource,
    BaseTable,
    get_name,
    make_datasource,
)
from app.modules.wip.models import Article

if TYPE_CHECKING:
    from flask import Flask


class TestGetName:
    """Tests for the get_name helper function."""

    def test_get_name_with_object(self):
        """Test get_name returns name when object has name."""
        obj = MagicMock()
        obj.name = "Test Name"
        assert get_name(obj) == "Test Name"

    def test_get_name_with_none(self):
        """Test get_name returns empty string for None."""
        assert get_name(None) == ""


class TestMakeDatasource:
    """Tests for the make_datasource factory function."""

    def test_make_datasource_creates_instance(self, app: Flask):
        """Test that make_datasource creates a BaseDataSource."""
        with app.test_request_context():
            ds = make_datasource(Article, "test")
            assert isinstance(ds, BaseDataSource)
            assert ds.model_class == Article
            assert ds.q == "test"


class TestBaseDataSource:
    """Tests for the BaseDataSource class."""

    def test_init_sets_limit_from_request(self, app: Flask):
        """Test that limit is set from request args."""
        with app.test_request_context("/?limit=20"):
            ds = BaseDataSource(model_class=Article, q="")
            assert ds.limit == 20

    def test_init_sets_offset_from_request(self, app: Flask):
        """Test that offset is set from request args."""
        with app.test_request_context("/?offset=50"):
            ds = BaseDataSource(model_class=Article, q="")
            assert ds.offset == 50

    def test_init_uses_default_limit(self, app: Flask):
        """Test that default limit is 10."""
        with app.test_request_context():
            ds = BaseDataSource(model_class=Article, q="")
            assert ds.limit == 10

    def test_init_uses_default_offset(self, app: Flask):
        """Test that default offset is 0."""
        with app.test_request_context():
            ds = BaseDataSource(model_class=Article, q="")
            assert ds.offset == 0

    def test_next_offset_increments(self, app: Flask):
        """Test next_offset increments by limit."""
        with app.test_request_context("/?offset=0&limit=10"):
            ds = BaseDataSource(model_class=Article, q="")
            # Mock get_count to return 100
            ds.get_count = MagicMock(return_value=100)
            assert ds.next_offset() == 10

    def test_next_offset_stays_at_end(self, app: Flask):
        """Test next_offset stays at current when at end."""
        with app.test_request_context("/?offset=90&limit=10"):
            ds = BaseDataSource(model_class=Article, q="")
            ds.get_count = MagicMock(return_value=95)
            # 90 + 10 = 100 >= 95, so stays at 90
            assert ds.next_offset() == 90

    def test_prev_offset_decrements(self, app: Flask):
        """Test prev_offset decrements by limit."""
        with app.test_request_context("/?offset=20&limit=10"):
            ds = BaseDataSource(model_class=Article, q="")
            assert ds.prev_offset() == 10

    def test_prev_offset_stops_at_zero(self, app: Flask):
        """Test prev_offset doesn't go below 0."""
        with app.test_request_context("/?offset=5&limit=10"):
            ds = BaseDataSource(model_class=Article, q="")
            assert ds.prev_offset() == 0


class TestBaseTable:
    """Tests for the BaseTable class."""

    def test_init_sets_query(self, app: Flask):
        """Test that init sets the query."""
        with app.test_request_context():
            table = BaseTable(Article, "search term")
            assert table.q == "search term"

    def test_columns_property(self, app: Flask):
        """Test that columns property returns get_columns result."""
        with app.test_request_context():
            table = BaseTable(Article)
            columns = table.columns
            assert isinstance(columns, list)
            assert len(columns) > 0

    def test_get_columns_returns_expected_structure(self, app: Flask):
        """Test get_columns returns expected column definitions."""
        with app.test_request_context():
            table = BaseTable(Article)
            columns = table.get_columns()

            # Should have titre, status, created_at, actions
            names = [c["name"] for c in columns]
            assert "titre" in names
            assert "status" in names
            assert "created_at" in names
            assert "$actions" in names

    def test_get_actions_returns_expected_actions(self, app: Flask):
        """Test get_actions returns view, edit, delete actions."""
        with app.test_request_context():
            table = BaseTable(Article)
            mock_item = MagicMock()
            mock_item.id = 1

            # Mock url_for
            table.url_for = MagicMock(
                side_effect=lambda item, action="get": (
                    f"/wip/articles/{item.id}/{action}"
                )
            )

            actions = table.get_actions(mock_item)
            assert len(actions) == 3
            labels = [a["label"] for a in actions]
            assert "Voir" in labels
            assert "Modifier" in labels
            assert "Supprimer" in labels

    def test_get_media_name_with_media(self, app: Flask):
        """Test get_media_name returns media name when present."""
        with app.test_request_context():
            table = BaseTable(Article)

            obj = MagicMock()
            obj.media = MagicMock()
            obj.media.name = "Test Media"

            assert table.get_media_name(obj) == "Test Media"

    def test_get_media_name_without_media(self, app: Flask):
        """Test get_media_name returns empty when no media."""
        with app.test_request_context():
            table = BaseTable(Article)

            obj = MagicMock()
            obj.media = None

            assert table.get_media_name(obj) == ""
