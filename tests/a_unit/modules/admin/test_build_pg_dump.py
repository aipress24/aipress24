# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Unit tests for admin/views.py - pure functions only.

This module tests only the pure functions from views.py that don't require
mocking or external system calls. Integration tests for the export_database
function should be in the integration test directory.
"""

from __future__ import annotations

import pytest
from sqlalchemy.engine import make_url

from app.modules.admin.views import _build_pg_dump_command


class TestBuildPgDumpCommand:
    """Test suite for _build_pg_dump_command function.

    This is a pure function that builds pg_dump commands from database URLs.
    It can be tested without mocks using real SQLAlchemy URL objects.
    """

    def test_build_pg_dump_command_with_full_config(self):
        """Test building pg_dump command with complete database URL.

        This test verifies that the function correctly builds a pg_dump command
        with all parameters including host, port, username, and password.
        """
        # ARRANGE: Create a PostgreSQL URL with all parameters
        db_url = make_url("postgresql://testuser:testpass@localhost:5432/testdb")

        # ACT: Call the function to build the command
        cmd, env = _build_pg_dump_command(db_url)

        # ASSERT: Verify the command and environment
        assert cmd == [
            "pg_dump",
            "--host",
            "localhost",
            "--port",
            "5432",
            "--format",
            "plain",
            "--no-owner",
            "--no-privileges",
            "--username",
            "testuser",
            "testdb",
        ]
        assert env == {"PGPASSWORD": "testpass"}

    def test_build_pg_dump_command_with_minimal_config(self):
        """Test building pg_dump command with minimal database URL.

        This test verifies that the function correctly handles URLs with
        minimal parameters and uses default values for missing ones.
        """
        # ARRANGE: Create a PostgreSQL URL with minimal parameters
        db_url = make_url("postgresql://localhost/testdb")

        # ACT: Call the function to build the command
        cmd, env = _build_pg_dump_command(db_url)

        # ASSERT: Verify the command and environment
        assert cmd == [
            "pg_dump",
            "--host",
            "localhost",
            "--port",
            "5432",
            "--format",
            "plain",
            "--no-owner",
            "--no-privileges",
            "testdb",
        ]
        assert env is None  # No password, so no environment needed

    def test_build_pg_dump_command_missing_database(self):
        """Test that ValueError is raised when database name is missing.

        This test verifies that the function properly validates the database URL
        and raises an appropriate error when the database name is missing.
        """
        # ARRANGE: Create a PostgreSQL URL without database name
        db_url = make_url("postgresql://localhost")

        # ACT & ASSERT: Verify that ValueError is raised
        with pytest.raises(ValueError, match="No database name found in database URL"):
            _build_pg_dump_command(db_url)

    def test_build_pg_dump_command_with_custom_port(self):
        """Test building pg_dump command with custom port.

        This test verifies that the function correctly handles custom port numbers.
        """
        # ARRANGE: Create a PostgreSQL URL with custom port
        db_url = make_url("postgresql://localhost:5433/testdb")

        # ACT: Call the function to build the command
        cmd, env = _build_pg_dump_command(db_url)

        # ASSERT: Verify the command includes the custom port
        assert "--port" in cmd
        assert "5433" in cmd
        assert env is None

    def test_build_pg_dump_command_without_username(self):
        """Test building pg_dump command without username.

        This test verifies that the function correctly handles URLs without username.
        """
        # ARRANGE: Create a PostgreSQL URL without username
        db_url = make_url("postgresql://localhost:5432/testdb")

        # ACT: Call the function to build the command
        cmd, env = _build_pg_dump_command(db_url)

        # ASSERT: Verify the command doesn't include username
        assert "--username" not in cmd
        assert "testdb" in cmd
        assert env is None
