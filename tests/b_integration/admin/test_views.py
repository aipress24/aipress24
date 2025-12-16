# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Integration tests for admin views - database export functionality."""

from __future__ import annotations

from collections.abc import Iterator
from typing import TYPE_CHECKING

import pytest
from flask import Flask
from sqlalchemy.engine import URL

from app.modules.admin.db_export_service import (
    DatabaseExportService,
    PgDumpConfig,
    PgDumpExecutionError,
    PgDumpNotFoundError,
)
from app.modules.admin.views import create_export_response

if TYPE_CHECKING:
    from flask.testing import FlaskClient


class StubExportService(DatabaseExportService):
    """Stub service that yields predefined data without calling pg_dump."""

    def __init__(self, config: PgDumpConfig):
        super().__init__(config)
        self._export_data = b"stub export data"

    def export_gzipped(self, chunk_size: int = 8192) -> Iterator[bytes]:
        """Return stub gzipped data."""
        yield self._export_data


class FailingExportService(DatabaseExportService):
    """Stub service that raises PgDumpExecutionError."""

    def export_gzipped(self, chunk_size: int = 8192) -> Iterator[bytes]:
        """Raise execution error."""
        raise PgDumpExecutionError(1, "connection refused")


class NotFoundExportService(DatabaseExportService):
    """Stub service that raises PgDumpNotFoundError."""

    def export_gzipped(self, chunk_size: int = 8192) -> Iterator[bytes]:
        """Raise not found error."""
        raise PgDumpNotFoundError("pg_dump not found")


class TestCreateExportResponse:
    """Tests for create_export_response function with stub services."""

    def test_successful_export_with_stub_service(self, app: Flask):
        """Test successful export using stub service."""
        url = URL.create(
            drivername="postgresql",
            username="testuser",
            password="testpass",
            host="localhost",
            port=5432,
            database="testdb",
        )

        with app.test_request_context():
            response = create_export_response(url, StubExportService)

            assert response.status_code == 200
            assert response.mimetype == "application/gzip"
            assert "attachment" in response.headers.get("Content-Disposition", "")
            assert "testdb_dump_" in response.headers.get("Content-Disposition", "")
            assert ".sql.gz" in response.headers.get("Content-Disposition", "")

            # Consume the generator to get the data
            data = b"".join(response.response)
            assert data == b"stub export data"

    def test_export_rejects_non_postgresql(self, app: Flask):
        """Test that non-PostgreSQL databases return 404."""
        url = URL.create(drivername="sqlite", database=":memory:")

        with app.test_request_context():
            with pytest.raises(Exception) as exc_info:
                create_export_response(url, StubExportService)
            # Flask abort raises werkzeug HTTPException
            assert "404" in str(exc_info.value) or exc_info.value.code == 404

    def test_export_rejects_mysql(self, app: Flask):
        """Test that MySQL databases return 404."""
        url = URL.create(drivername="mysql", database="testdb", host="localhost")

        with app.test_request_context():
            with pytest.raises(Exception) as exc_info:
                create_export_response(url, StubExportService)
            assert "404" in str(exc_info.value) or exc_info.value.code == 404

    def test_export_handles_missing_database_name(self, app: Flask):
        """Test that missing database name returns 500."""
        url = URL.create(drivername="postgresql", host="localhost")

        with app.test_request_context():
            with pytest.raises(Exception) as exc_info:
                create_export_response(url, StubExportService)
            assert "500" in str(exc_info.value) or exc_info.value.code == 500

    def test_export_with_psycopg2_driver(self, app: Flask):
        """Test export works with postgresql+psycopg2 driver."""
        url = URL.create(
            drivername="postgresql+psycopg2",
            host="localhost",
            database="testdb",
        )

        with app.test_request_context():
            response = create_export_response(url, StubExportService)
            assert response.status_code == 200

    def test_response_headers_security(self, app: Flask):
        """Test that response has proper security headers."""
        url = URL.create(
            drivername="postgresql",
            host="localhost",
            database="testdb",
        )

        with app.test_request_context():
            response = create_export_response(url, StubExportService)
            assert response.headers.get("X-Content-Type-Options") == "nosniff"


class TestExportErrorHandling:
    """Tests for error handling in export view."""

    def test_pg_dump_execution_error_propagates(self, app: Flask):
        """Test that PgDumpExecutionError propagates through the generator."""
        url = URL.create(
            drivername="postgresql",
            host="localhost",
            database="testdb",
        )

        with app.test_request_context():
            response = create_export_response(url, FailingExportService)
            # Error happens when consuming the generator
            with pytest.raises(PgDumpExecutionError) as exc_info:
                list(response.response)
            assert exc_info.value.return_code == 1
            assert "connection refused" in exc_info.value.stderr

    def test_pg_dump_not_found_error_propagates(self, app: Flask):
        """Test that PgDumpNotFoundError propagates through the generator."""
        url = URL.create(
            drivername="postgresql",
            host="localhost",
            database="testdb",
        )

        with app.test_request_context():
            response = create_export_response(url, NotFoundExportService)
            with pytest.raises(PgDumpNotFoundError):
                list(response.response)


class TestExportDatabaseRoute:
    """Integration tests for the /export-db/ route with stub services."""

    def test_route_returns_404_for_sqlite(self, admin_client: FlaskClient):
        """Test that export route returns 404 when using SQLite (test db)."""
        # The test database uses SQLite, so this should return 404
        response = admin_client.get("/admin/export-db/")
        assert response.status_code == 404
