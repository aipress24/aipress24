# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Integration tests for db_export_service against the LIVE engine URL.

The a_unit suite already covers PgDumpConfig / DatabaseExportService with
mocks (URL.create() instances, MagicMock subprocesses). This file lives
at the b_integration tier because it exercises the pure helpers against
the REAL SQLAlchemy engine URL produced by the running Flask app — the
same object that the production view (`views/db_export.py`) passes in.

The subprocess-calling paths (`export_gzipped` / `export_raw`) are NOT
covered here: they actually shell out to pg_dump, so they belong at the
c_e2e tier (or stay mocked in a_unit). We focus on:

- is_postgresql_database() applied to the live engine URL
- PgDumpConfig.from_url() round-tripping the live URL's components
- build_command() / build_env() producing a valid argv given that config
- DatabaseExportService.generate_filename() formatting against the
  database name actually used by the test session

No mocks, no monkeypatch, no MagicMock — per CLAUDE.md.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

import pytest
from sqlalchemy.engine import URL

from app.flask.extensions import db
from app.modules.admin.db_export_service import (
    DatabaseExportService,
    PgDumpConfig,
    is_postgresql_database,
)

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


@pytest.fixture
def live_url(db_session: Session) -> URL:
    """Return the actual SQLAlchemy URL of the bound test engine.

    The `db_session` fixture is requested only to guarantee the engine
    is bound and the app context is active for this test.
    """
    _ = db_session  # tie fixture lifecycle to the live transaction
    return db.engine.url


class TestIsPostgresqlAgainstLiveEngine:
    """Drive is_postgresql_database with the URL of the running engine."""

    def test_detects_driver_family_of_live_engine(self, live_url: URL) -> None:
        # Whatever the test backend is (sqlite or postgresql+psycopg), the
        # detector's verdict must match the drivername prefix.
        expected = live_url.drivername.startswith("postgresql")
        assert is_postgresql_database(live_url) is expected

    def test_live_engine_drivername_is_known_family(self, live_url: URL) -> None:
        # Sanity: we only ever run tests on sqlite or postgresql, so the
        # detector must give a definite True/False — never raise.
        assert live_url.drivername.split("+", 1)[0] in {"sqlite", "postgresql"}
        assert isinstance(is_postgresql_database(live_url), bool)


class TestPgDumpConfigRoundTripFromLiveURL:
    """PgDumpConfig.from_url must accept the engine URL as-is."""

    def test_from_url_preserves_database_field(self, live_url: URL) -> None:
        if not live_url.database:
            pytest.skip("Live URL has no database (rare); covered in a_unit.")
        cfg = PgDumpConfig.from_url(live_url)
        assert cfg.database == live_url.database

    def test_from_url_defaults_host_and_port(self, live_url: URL) -> None:
        if not live_url.database:
            pytest.skip("Live URL has no database; nothing to assert.")
        cfg = PgDumpConfig.from_url(live_url)
        # When host/port are unset on the engine URL, the config must fall
        # back to the documented defaults — never None / never 0.
        assert cfg.host == (live_url.host or "localhost")
        assert cfg.port == (live_url.port or 5432)

    def test_from_url_propagates_credentials(self, live_url: URL) -> None:
        if not live_url.database:
            pytest.skip("Live URL has no database; nothing to assert.")
        cfg = PgDumpConfig.from_url(live_url)
        assert cfg.username == live_url.username
        assert cfg.password == live_url.password


class TestBuildCommandFromLiveConfig:
    """The argv list produced from the live URL must be well-formed."""

    def test_command_starts_with_pg_dump_and_ends_with_database(
        self, live_url: URL
    ) -> None:
        if not live_url.database:
            pytest.skip("Live URL has no database; cannot build a command.")
        cfg = PgDumpConfig.from_url(live_url)
        cmd = cfg.build_command()

        assert cmd[0] == "pg_dump"
        assert cmd[-1] == cfg.database

    @pytest.mark.parametrize(
        "required_flag",
        ["--host", "--port", "--format", "--no-owner", "--no-privileges"],
    )
    def test_command_includes_required_flag(
        self, live_url: URL, required_flag: str
    ) -> None:
        if not live_url.database:
            pytest.skip("Live URL has no database; cannot build a command.")
        cmd = PgDumpConfig.from_url(live_url).build_command()
        assert required_flag in cmd

    def test_username_flag_presence_matches_url(self, live_url: URL) -> None:
        if not live_url.database:
            pytest.skip("Live URL has no database; cannot build a command.")
        cmd = PgDumpConfig.from_url(live_url).build_command()
        if live_url.username:
            assert "--username" in cmd
            assert live_url.username in cmd
        else:
            assert "--username" not in cmd

    def test_env_presence_matches_password(self, live_url: URL) -> None:
        if not live_url.database:
            pytest.skip("Live URL has no database; nothing to assert.")
        env = PgDumpConfig.from_url(live_url).build_env()
        if live_url.password:
            assert env is not None
            assert env["PGPASSWORD"] == live_url.password
        else:
            assert env is None


class TestGenerateFilenameAgainstLiveDatabase:
    """`generate_filename` must produce a sortable, timestamped name."""

    _FILENAME_RE = re.compile(r"^(?P<db>.+)_dump_(?P<ts>\d{8}_\d{6})\.sql\.gz$")

    def test_filename_matches_documented_pattern(self, live_url: URL) -> None:
        if not live_url.database:
            pytest.skip("Live URL has no database; filename is meaningless.")
        service = DatabaseExportService(PgDumpConfig.from_url(live_url))
        name = service.generate_filename()

        match = self._FILENAME_RE.match(name)
        assert match is not None, f"unexpected filename: {name!r}"
        assert match.group("db") == live_url.database

    def test_database_name_property_matches_url(self, live_url: URL) -> None:
        if not live_url.database:
            pytest.skip("Live URL has no database; nothing to expose.")
        service = DatabaseExportService(PgDumpConfig.from_url(live_url))
        assert service.database_name == live_url.database


class TestNonPostgresGuardWithLiveURL:
    """
    The view layer guards on is_postgresql_database() BEFORE calling
    PgDumpConfig.from_url(). Verify the guard's verdict is consistent
    with what from_url() would accept for the live URL.
    """

    def test_guard_and_config_agree_on_live_url(self, live_url: URL) -> None:
        # If the guard says yes, from_url must succeed; if it says no, the
        # view rejects the request before from_url is ever called, so we
        # only assert success on the postgres branch.
        if is_postgresql_database(live_url) and live_url.database:
            cfg = PgDumpConfig.from_url(live_url)
            assert cfg.database == live_url.database
        elif live_url.database:
            # Non-postgres live URL still parses; the guard is what rejects
            # the request, not from_url(). Confirm from_url() doesn't crash
            # on a non-postgres URL with a database name.
            cfg = PgDumpConfig.from_url(live_url)
            assert cfg.database == live_url.database
