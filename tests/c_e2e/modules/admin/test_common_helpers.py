# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""E2E tests for admin _common helper functions."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock

if TYPE_CHECKING:
    from flask import Flask



class TestBuildUrl:
    """Tests for the build_url helper function."""

    def test_build_url_no_params(self, app: Flask):
        """Test build_url with no params returns base URL."""
        from app.modules.admin.views._common import build_url

        with app.test_request_context():
            url = build_url("admin.users")
            assert url == "/admin/users"

    def test_build_url_with_offset(self, app: Flask):
        """Test build_url with offset parameter."""
        from app.modules.admin.views._common import build_url

        with app.test_request_context():
            url = build_url("admin.users", offset=10)
            assert url == "/admin/users?offset=10"

    def test_build_url_with_search(self, app: Flask):
        """Test build_url with search parameter."""
        from app.modules.admin.views._common import build_url

        with app.test_request_context():
            url = build_url("admin.users", search="test")
            assert url == "/admin/users?search=test"

    def test_build_url_with_offset_and_search(self, app: Flask):
        """Test build_url with both offset and search."""
        from app.modules.admin.views._common import build_url

        with app.test_request_context():
            url = build_url("admin.users", offset=20, search="query")
            assert "offset=20" in url
            assert "search=query" in url

    def test_build_url_zero_offset_not_included(self, app: Flask):
        """Test that zero offset is not included in URL."""
        from app.modules.admin.views._common import build_url

        with app.test_request_context():
            url = build_url("admin.users", offset=0)
            assert "offset" not in url

    def test_build_url_empty_search_not_included(self, app: Flask):
        """Test that empty search is not included in URL."""
        from app.modules.admin.views._common import build_url

        with app.test_request_context():
            url = build_url("admin.users", search="")
            assert "search" not in url


class TestBuildTableContext:
    """Tests for the build_table_context helper function."""

    def test_build_table_context_returns_dict(self, app: Flask):
        """Test that build_table_context returns expected structure."""
        from app.modules.admin.views._common import build_table_context

        # Create mock classes
        mock_ds_class = MagicMock()
        mock_ds_instance = MagicMock()
        mock_ds_instance.records.return_value = []
        mock_ds_instance.offset = 0
        mock_ds_instance.limit = 10
        mock_ds_instance.count.return_value = 0
        mock_ds_instance.search = ""
        mock_ds_class.return_value = mock_ds_instance

        mock_table_class = MagicMock()
        mock_table_instance = MagicMock()
        mock_table_class.return_value = mock_table_instance

        with app.test_request_context():
            context = build_table_context(mock_ds_class, mock_table_class)

        assert "table" in context
        assert "ds" in context
        assert context["ds"] == mock_ds_instance

    def test_build_table_context_sets_table_attrs(self, app: Flask):
        """Test that build_table_context sets table attributes."""
        from app.modules.admin.views._common import build_table_context

        mock_ds_class = MagicMock()
        mock_ds_instance = MagicMock()
        mock_ds_instance.records.return_value = [1, 2, 3]
        mock_ds_instance.offset = 0
        mock_ds_instance.limit = 10
        mock_ds_instance.count.return_value = 50
        mock_ds_instance.search = "test"
        mock_ds_class.return_value = mock_ds_instance

        mock_table_class = MagicMock()
        mock_table_instance = MagicMock()
        mock_table_class.return_value = mock_table_instance

        with app.test_request_context():
            context = build_table_context(mock_ds_class, mock_table_class)

        table = context["table"]
        assert table.start == 1
        assert table.end == 10  # min(offset + limit, count) = min(10, 50)
        assert table.count == 50
        assert table.searching == "test"


class TestHandleTablePost:
    """Tests for the handle_table_post helper function."""

    def test_handle_table_post_next(self, app: Flask):
        """Test handle_table_post with next action."""
        from app.modules.admin.views._common import handle_table_post

        mock_ds_class = MagicMock()
        mock_ds_instance = MagicMock()
        mock_ds_instance.next_offset.return_value = 10
        mock_ds_instance.search = ""
        mock_ds_class.return_value = mock_ds_instance

        with app.test_request_context(method="POST", data={"action": "next"}):
            response = handle_table_post(mock_ds_class, "admin.users")

        assert response.status_code == 200
        assert "HX-Redirect" in response.headers
        assert "offset=10" in response.headers["HX-Redirect"]

    def test_handle_table_post_previous(self, app: Flask):
        """Test handle_table_post with previous action."""
        from app.modules.admin.views._common import handle_table_post

        mock_ds_class = MagicMock()
        mock_ds_instance = MagicMock()
        mock_ds_instance.prev_offset.return_value = 0
        mock_ds_instance.search = ""
        mock_ds_class.return_value = mock_ds_instance

        with app.test_request_context(method="POST", data={"action": "previous"}):
            response = handle_table_post(mock_ds_class, "admin.users")

        assert response.status_code == 200
        assert "HX-Redirect" in response.headers

    def test_handle_table_post_search(self, app: Flask):
        """Test handle_table_post with search action."""
        from app.modules.admin.views._common import handle_table_post

        mock_ds_class = MagicMock()
        mock_ds_instance = MagicMock()
        mock_ds_instance.search = ""
        mock_ds_instance.offset = 0
        mock_ds_class.return_value = mock_ds_instance

        with app.test_request_context(method="POST", data={"search": "query"}):
            response = handle_table_post(mock_ds_class, "admin.users")

        assert response.status_code == 200
        assert "HX-Redirect" in response.headers
        assert "search=query" in response.headers["HX-Redirect"]

    def test_handle_table_post_search_same_resets_offset(self, app: Flask):
        """Test that same search query keeps offset, new search resets."""
        from app.modules.admin.views._common import handle_table_post

        mock_ds_class = MagicMock()
        mock_ds_instance = MagicMock()
        mock_ds_instance.search = "existing"
        mock_ds_instance.offset = 20
        mock_ds_class.return_value = mock_ds_instance

        # New search should reset offset to 0
        with app.test_request_context(method="POST", data={"search": "new_query"}):
            response = handle_table_post(mock_ds_class, "admin.users")

        assert "offset" not in response.headers["HX-Redirect"]

    def test_handle_table_post_no_action(self, app: Flask):
        """Test handle_table_post with no action redirects to base."""
        from app.modules.admin.views._common import handle_table_post

        mock_ds_class = MagicMock()
        mock_ds_instance = MagicMock()
        mock_ds_class.return_value = mock_ds_instance

        with app.test_request_context(method="POST", data={}):
            response = handle_table_post(mock_ds_class, "admin.users")

        assert response.status_code == 200
        assert "HX-Redirect" in response.headers
        assert response.headers["HX-Redirect"] == "/admin/users"

    def test_handle_table_post_next_with_search(self, app: Flask):
        """Test handle_table_post next action preserves search."""
        from app.modules.admin.views._common import handle_table_post

        mock_ds_class = MagicMock()
        mock_ds_instance = MagicMock()
        mock_ds_instance.next_offset.return_value = 10
        mock_ds_instance.search = "preserved"
        mock_ds_class.return_value = mock_ds_instance

        with app.test_request_context(method="POST", data={"action": "next"}):
            response = handle_table_post(mock_ds_class, "admin.users")

        assert "offset=10" in response.headers["HX-Redirect"]
        assert "search=preserved" in response.headers["HX-Redirect"]
