# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Unit tests for DatabaseExportService."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy.engine import URL

from app.modules.admin.db_export_service import (
    DatabaseExportError,
    DatabaseExportService,
    PgDumpConfig,
    PgDumpExecutionError,
    PgDumpNotFoundError,
    is_postgresql_database,
)


class TestPgDumpConfig:
    """Tests for PgDumpConfig dataclass."""

    def test_from_url_with_full_url(self):
        """Test creating config from full database URL."""
        url = URL.create(
            drivername="postgresql",
            username="testuser",
            password="testpass",
            host="testhost",
            port=5433,
            database="testdb",
        )

        config = PgDumpConfig.from_url(url)

        assert config.host == "testhost"
        assert config.port == 5433
        assert config.database == "testdb"
        assert config.username == "testuser"
        assert config.password == "testpass"

    def test_from_url_with_defaults(self):
        """Test creating config with default host and port."""
        url = URL.create(
            drivername="postgresql",
            database="testdb",
        )

        config = PgDumpConfig.from_url(url)

        assert config.host == "localhost"
        assert config.port == 5432
        assert config.database == "testdb"
        assert config.username is None
        assert config.password is None

    def test_from_url_raises_on_missing_database(self):
        """Test that ValueError is raised when database name is missing."""
        url = URL.create(
            drivername="postgresql",
            host="testhost",
        )

        with pytest.raises(ValueError, match="No database name found"):
            PgDumpConfig.from_url(url)

    def test_build_command_basic(self):
        """Test building pg_dump command without username."""
        config = PgDumpConfig(
            host="localhost",
            port=5432,
            database="mydb",
        )

        cmd = config.build_command()

        assert cmd[0] == "pg_dump"
        assert "--host" in cmd
        assert "localhost" in cmd
        assert "--port" in cmd
        assert "5432" in cmd
        assert "--format" in cmd
        assert "plain" in cmd
        assert "--no-owner" in cmd
        assert "--no-privileges" in cmd
        assert "mydb" in cmd
        assert "--username" not in cmd

    def test_build_command_with_username(self):
        """Test building pg_dump command with username."""
        config = PgDumpConfig(
            host="localhost",
            port=5432,
            database="mydb",
            username="admin",
        )

        cmd = config.build_command()

        assert "--username" in cmd
        assert "admin" in cmd

    def test_build_env_without_password(self):
        """Test building environment without password."""
        config = PgDumpConfig(
            host="localhost",
            port=5432,
            database="mydb",
        )

        env = config.build_env()

        assert env is None

    def test_build_env_with_password(self):
        """Test building environment with password."""
        config = PgDumpConfig(
            host="localhost",
            port=5432,
            database="mydb",
            password="secret",
        )

        env = config.build_env()

        assert env is not None
        assert env["PGPASSWORD"] == "secret"


class TestDatabaseExportService:
    """Tests for DatabaseExportService class."""

    def test_database_name_property(self):
        """Test database_name property returns correct value."""
        config = PgDumpConfig(
            host="localhost",
            port=5432,
            database="mydb",
        )
        service = DatabaseExportService(config)

        assert service.database_name == "mydb"

    def test_generate_filename_format(self):
        """Test generate_filename returns correct format."""
        config = PgDumpConfig(
            host="localhost",
            port=5432,
            database="testdb",
        )
        service = DatabaseExportService(config)

        filename = service.generate_filename()

        assert filename.startswith("testdb_dump_")
        assert filename.endswith(".sql.gz")
        # Check timestamp format (YYYYMMDD_HHMMSS)
        parts = filename.replace("testdb_dump_", "").replace(".sql.gz", "")
        assert len(parts) == 15  # YYYYMMDD_HHMMSS

    @patch("app.modules.admin.db_export_service.subprocess.Popen")
    def test_export_gzipped_success(self, mock_popen):
        """Test successful gzipped export."""
        # Setup mock process
        mock_process = MagicMock()
        mock_process.stdout.read.side_effect = [b"test data", b""]
        mock_process.wait.return_value = 0
        mock_popen.return_value = mock_process

        config = PgDumpConfig(
            host="localhost",
            port=5432,
            database="testdb",
        )
        service = DatabaseExportService(config)

        # Collect all chunks
        chunks = list(service.export_gzipped())

        # Should have produced some compressed output
        assert len(chunks) > 0
        # Gzip header starts with 0x1f 0x8b
        all_data = b"".join(chunks)
        assert all_data[:2] == b"\x1f\x8b"

    @patch("app.modules.admin.db_export_service.subprocess.Popen")
    def test_export_gzipped_pg_dump_fails(self, mock_popen):
        """Test handling of pg_dump failure."""
        mock_process = MagicMock()
        mock_process.stdout.read.side_effect = [b""]
        mock_process.stderr.read.return_value = b"connection refused"
        mock_process.wait.return_value = 1
        mock_popen.return_value = mock_process

        config = PgDumpConfig(
            host="localhost",
            port=5432,
            database="testdb",
        )
        service = DatabaseExportService(config)

        with pytest.raises(PgDumpExecutionError) as exc_info:
            list(service.export_gzipped())

        assert exc_info.value.return_code == 1
        assert "connection refused" in exc_info.value.stderr

    @patch("app.modules.admin.db_export_service.subprocess.Popen")
    def test_export_gzipped_pg_dump_not_found(self, mock_popen):
        """Test handling of missing pg_dump command."""
        mock_popen.side_effect = FileNotFoundError("pg_dump not found")

        config = PgDumpConfig(
            host="localhost",
            port=5432,
            database="testdb",
        )
        service = DatabaseExportService(config)

        with pytest.raises(PgDumpNotFoundError):
            list(service.export_gzipped())

    @patch("app.modules.admin.db_export_service.subprocess.Popen")
    def test_export_raw_success(self, mock_popen):
        """Test successful raw export."""
        mock_process = MagicMock()
        mock_process.stdout.read.side_effect = [b"CREATE TABLE", b" test;", b""]
        mock_process.wait.return_value = 0
        mock_popen.return_value = mock_process

        config = PgDumpConfig(
            host="localhost",
            port=5432,
            database="testdb",
        )
        service = DatabaseExportService(config)

        chunks = list(service.export_raw())

        assert b"CREATE TABLE" in b"".join(chunks)


class TestIsPostgresqlDatabase:
    """Tests for is_postgresql_database function."""

    def test_postgresql_driver(self):
        """Test detection of PostgreSQL database."""
        url = URL.create(drivername="postgresql", database="test")
        assert is_postgresql_database(url) is True

    def test_postgresql_psycopg2_driver(self):
        """Test detection of PostgreSQL with psycopg2 driver."""
        url = URL.create(drivername="postgresql+psycopg2", database="test")
        assert is_postgresql_database(url) is True

    def test_sqlite_driver(self):
        """Test SQLite is not detected as PostgreSQL."""
        url = URL.create(drivername="sqlite", database=":memory:")
        assert is_postgresql_database(url) is False

    def test_mysql_driver(self):
        """Test MySQL is not detected as PostgreSQL."""
        url = URL.create(drivername="mysql", database="test")
        assert is_postgresql_database(url) is False


class TestDatabaseExportErrors:
    """Tests for custom exception classes."""

    def test_database_export_error_is_exception(self):
        """Test DatabaseExportError is an Exception."""
        assert issubclass(DatabaseExportError, Exception)

    def test_pg_dump_not_found_error(self):
        """Test PgDumpNotFoundError creation."""
        error = PgDumpNotFoundError("pg_dump not found")
        assert str(error) == "pg_dump not found"
        assert isinstance(error, DatabaseExportError)

    def test_pg_dump_execution_error(self):
        """Test PgDumpExecutionError creation."""
        error = PgDumpExecutionError(1, "connection refused")
        assert error.return_code == 1
        assert error.stderr == "connection refused"
        assert "1" in str(error)
        assert "connection refused" in str(error)
        assert isinstance(error, DatabaseExportError)
