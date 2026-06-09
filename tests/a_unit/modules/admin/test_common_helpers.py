# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""E2E tests for admin _common helper functions."""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.modules.admin.views._common import (
    build_table_context,
    build_url,
    handle_table_post,
)

if TYPE_CHECKING:
    from flask import Flask


class _DataSource:
    """Stand-in for a datasource used by the admin table helpers."""

    def __init__(
        self,
        *,
        records: list | None = None,
        offset: int = 0,
        limit: int = 10,
        count: int = 0,
        search: str = "",
        next_offset: int = 0,
        prev_offset: int = 0,
    ) -> None:
        self._records = records if records is not None else []
        self.offset = offset
        self.limit = limit
        self._count = count
        self.search = search
        self._next_offset = next_offset
        self._prev_offset = prev_offset

    def records(self) -> list:
        return self._records

    def count(self) -> int:
        return self._count

    def next_offset(self) -> int:
        return self._next_offset

    def prev_offset(self) -> int:
        return self._prev_offset


class _Table:
    """Stand-in table object that just collects attributes set on it."""

    def __init__(self, records: list) -> None:
        self.records = records


def _ds_factory(ds: _DataSource):
    """Wrap a prebuilt _DataSource so the SUT can call it with no args."""

    def _factory() -> _DataSource:
        return ds

    return _factory


def _table_factory(table_cls=_Table):
    """Return a callable that builds a `_Table` from records."""

    def _factory(records):
        return table_cls(records)

    return _factory


class TestBuildUrl:
    """Tests for the build_url helper function."""

    def test_build_url_no_params(self, app: Flask):
        """Test build_url with no params returns base URL."""
        with app.test_request_context():
            url = build_url("admin.users")
            assert url == "/admin/users"

    def test_build_url_with_offset(self, app: Flask):
        """Test build_url with offset parameter."""
        with app.test_request_context():
            url = build_url("admin.users", offset=10)
            assert url == "/admin/users?offset=10"

    def test_build_url_with_search(self, app: Flask):
        """Test build_url with search parameter."""
        with app.test_request_context():
            url = build_url("admin.users", search="test")
            assert url == "/admin/users?search=test"

    def test_build_url_with_offset_and_search(self, app: Flask):
        """Test build_url with both offset and search."""
        with app.test_request_context():
            url = build_url("admin.users", offset=20, search="query")
            assert "offset=20" in url
            assert "search=query" in url

    def test_build_url_zero_offset_not_included(self, app: Flask):
        """Test that zero offset is not included in URL."""
        with app.test_request_context():
            url = build_url("admin.users", offset=0)
            assert "offset" not in url

    def test_build_url_empty_search_not_included(self, app: Flask):
        """Test that empty search is not included in URL."""
        with app.test_request_context():
            url = build_url("admin.users", search="")
            assert "search" not in url


class TestBuildTableContext:
    """Tests for the build_table_context helper function."""

    def test_build_table_context_returns_dict(self, app: Flask):
        """Test that build_table_context returns expected structure."""
        ds = _DataSource(records=[], offset=0, limit=10, count=0, search="")

        with app.test_request_context():
            context = build_table_context(_ds_factory(ds), _table_factory())

        assert "table" in context
        assert "ds" in context
        assert context["ds"] is ds

    def test_build_table_context_sets_table_attrs(self, app: Flask):
        """Test that build_table_context sets table attributes."""
        ds = _DataSource(records=[1, 2, 3], offset=0, limit=10, count=50, search="test")

        with app.test_request_context():
            context = build_table_context(_ds_factory(ds), _table_factory())

        table = context["table"]
        assert table.start == 1
        assert table.end == 10  # min(offset + limit, count) = min(10, 50)
        assert table.count == 50
        assert table.searching == "test"


class TestHandleTablePost:
    """Tests for the handle_table_post helper function."""

    def test_handle_table_post_next(self, app: Flask):
        """Test handle_table_post with next action."""
        ds = _DataSource(next_offset=10, search="")

        with app.test_request_context(method="POST", data={"action": "next"}):
            response = handle_table_post(_ds_factory(ds), "admin.users")

        assert response.status_code == 200
        assert "HX-Redirect" in response.headers
        assert "offset=10" in response.headers["HX-Redirect"]

    def test_handle_table_post_previous(self, app: Flask):
        """Test handle_table_post with previous action."""
        ds = _DataSource(prev_offset=0, search="")

        with app.test_request_context(method="POST", data={"action": "previous"}):
            response = handle_table_post(_ds_factory(ds), "admin.users")

        assert response.status_code == 200
        assert "HX-Redirect" in response.headers

    def test_handle_table_post_search(self, app: Flask):
        """Test handle_table_post with search action."""
        ds = _DataSource(search="", offset=0)

        with app.test_request_context(method="POST", data={"search": "query"}):
            response = handle_table_post(_ds_factory(ds), "admin.users")

        assert response.status_code == 200
        assert "HX-Redirect" in response.headers
        assert "search=query" in response.headers["HX-Redirect"]

    def test_handle_table_post_search_same_resets_offset(self, app: Flask):
        """Test that same search query keeps offset, new search resets."""
        ds = _DataSource(search="existing", offset=20)

        # New search should reset offset to 0
        with app.test_request_context(method="POST", data={"search": "new_query"}):
            response = handle_table_post(_ds_factory(ds), "admin.users")

        assert "offset" not in response.headers["HX-Redirect"]

    def test_handle_table_post_no_action(self, app: Flask):
        """Test handle_table_post with no action redirects to base."""
        ds = _DataSource()

        with app.test_request_context(method="POST", data={}):
            response = handle_table_post(_ds_factory(ds), "admin.users")

        assert response.status_code == 200
        assert "HX-Redirect" in response.headers
        assert response.headers["HX-Redirect"] == "/admin/users"

    def test_handle_table_post_next_with_search(self, app: Flask):
        """Test handle_table_post next action preserves search."""
        ds = _DataSource(next_offset=10, search="preserved")

        with app.test_request_context(method="POST", data={"action": "next"}):
            response = handle_table_post(_ds_factory(ds), "admin.users")

        assert "offset=10" in response.headers["HX-Redirect"]
        assert "search=preserved" in response.headers["HX-Redirect"]
