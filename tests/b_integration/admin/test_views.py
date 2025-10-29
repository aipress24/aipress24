# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Tests for admin/views module."""

from __future__ import annotations

import pytest
from sqlalchemy.engine import make_url

from app.modules.admin.views import _build_pg_dump_command


class TestBuildPgDumpCommand:
    """Test suite for _build_pg_dump_command function."""

    def test_basic_url_with_all_parameters(self):
        """Test building command with all URL parameters."""
        db_url = make_url("postgresql://user:pass@localhost:5432/testdb")

        cmd, env = _build_pg_dump_command(db_url)

        assert "pg_dump" in cmd
        assert "--host" in cmd
        assert "localhost" in cmd
        assert "--port" in cmd
        assert "5432" in cmd
        assert "--username" in cmd
        assert "user" in cmd
        assert "testdb" in cmd
        assert "--format" in cmd
        assert "plain" in cmd
        assert "--no-owner" in cmd
        assert "--no-privileges" in cmd

        assert env is not None
        assert env["PGPASSWORD"] == "pass"

    def test_url_without_password(self):
        """Test building command without password."""
        db_url = make_url("postgresql://user@localhost:5432/testdb")

        cmd, env = _build_pg_dump_command(db_url)

        assert "--username" in cmd
        assert "user" in cmd
        assert "testdb" in cmd

        # No environment needed without password
        assert env is None

    def test_url_without_username(self):
        """Test building command without username."""
        db_url = make_url("postgresql://localhost:5432/testdb")

        cmd, env = _build_pg_dump_command(db_url)

        assert "--username" not in cmd
        assert "testdb" in cmd

    def test_url_defaults_host_and_port(self):
        """Test that missing host and port get defaults."""
        # Create a URL with minimal info
        db_url = make_url("postgresql:///testdb")

        cmd, env = _build_pg_dump_command(db_url)

        # Should default to localhost:5432
        assert "--host" in cmd
        assert "localhost" in cmd
        assert "--port" in cmd
        assert "5432" in cmd

    def test_url_with_custom_port(self):
        """Test building command with custom port."""
        db_url = make_url("postgresql://user@localhost:5433/testdb")

        cmd, env = _build_pg_dump_command(db_url)

        assert "--port" in cmd
        assert "5433" in cmd

    def test_url_without_database_raises_error(self):
        """Test that URL without database name raises ValueError."""
        # URL without database name
        db_url = make_url("postgresql://user@localhost:5432/")

        with pytest.raises(ValueError, match="No database name found"):
            _build_pg_dump_command(db_url)

    def test_command_order(self):
        """Test that command has correct structure."""
        db_url = make_url("postgresql://user:pass@localhost:5432/testdb")

        cmd, env = _build_pg_dump_command(db_url)

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
        """Test that password is only in environment, not in command."""
        db_url = make_url("postgresql://user:secret123@localhost:5432/testdb")

        cmd, env = _build_pg_dump_command(db_url)

        # Password should not be in command
        assert "secret123" not in cmd
        assert "secret123" not in " ".join(cmd)

        # But should be in environment
        assert env is not None
        assert env["PGPASSWORD"] == "secret123"
