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

    def test_url_without_password(self):
        """Test building command without password.

        This test verifies that the function correctly handles URLs without password.
        """
        # ARRANGE: Create a PostgreSQL URL without password
        db_url = make_url("postgresql://user@localhost:5432/testdb")

        # ACT: Call the function to build the command
        cmd, env = _build_pg_dump_command(db_url)

        # ASSERT: Verify the command and environment
        assert "--username" in cmd
        assert "user" in cmd
        assert "testdb" in cmd

        # No environment needed without password
        assert env is None

    def test_url_defaults_host_and_port(self):
        """Test that missing host and port get defaults.

        This test verifies that the function uses default values for missing
        host and port parameters.
        """
        # ARRANGE: Create a URL with minimal info
        db_url = make_url("postgresql:///testdb")

        # ACT: Call the function to build the command
        cmd, env = _build_pg_dump_command(db_url)

        # ASSERT: Verify defaults are used
        # Should default to localhost:5432
        assert "--host" in cmd
        assert "localhost" in cmd
        assert "--port" in cmd
        assert "5432" in cmd

    def test_command_order(self):
        """Test that command has correct structure.

        This test verifies that the command has the correct order and structure.
        """
        # ARRANGE: Create a complete PostgreSQL URL
        db_url = make_url("postgresql://user:pass@localhost:5432/testdb")

        # ACT: Call the function to build the command
        cmd, env = _build_pg_dump_command(db_url)

        # ASSERT: Verify command structure
        # pg_dump should be first
        assert cmd[0] == "pg_dump"

        # Database should be last
        assert cmd[-1] == "testdb"

        # Flags should be present
        assert "--format" in cmd
        assert "plain" in cmd
        assert "--no-owner" in cmd
        assert "--no-privileges" in cmd

    def test_password_in_environment_only(self):
        """Test that password is only in environment, not in command.

        This test verifies that the password is properly handled in the environment
        and not exposed in the command line.
        """
        # ARRANGE: Create a PostgreSQL URL with password
        db_url = make_url("postgresql://user:secret123@localhost:5432/testdb")

        # ACT: Call the function to build the command
        cmd, env = _build_pg_dump_command(db_url)

        # ASSERT: Verify password handling
        # Password should not be in command
        assert "secret123" not in cmd
        assert "secret123" not in " ".join(cmd)

        # But should be in environment
        assert env is not None
        assert env["PGPASSWORD"] == "secret123"
