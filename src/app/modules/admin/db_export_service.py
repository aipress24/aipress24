# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Database export service for PostgreSQL databases.

This module provides a service class for exporting PostgreSQL databases
using pg_dump. The service is designed to be testable by separating
the core logic from HTTP handling.
"""

from __future__ import annotations

import subprocess
import zlib
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from loguru import logger

if TYPE_CHECKING:
    from sqlalchemy.engine import URL


@dataclass(frozen=True)
class PgDumpConfig:
    """Configuration for pg_dump command."""

    host: str
    port: int
    database: str
    username: str | None = None
    password: str | None = None

    @classmethod
    def from_url(cls, db_url: URL) -> PgDumpConfig:
        """Create config from SQLAlchemy database URL.

        Args:
            db_url: SQLAlchemy database URL

        Returns:
            PgDumpConfig instance

        Raises:
            ValueError: If database name is missing from URL
        """
        database = db_url.database
        if not database:
            msg = "No database name found in database URL"
            raise ValueError(msg)

        return cls(
            host=db_url.host or "localhost",
            port=db_url.port or 5432,
            database=database,
            username=db_url.username,
            password=db_url.password,
        )

    def build_command(self) -> list[str]:
        """Build pg_dump command arguments.

        Returns:
            List of command arguments for pg_dump
        """
        cmd = [
            "pg_dump",
            "--host",
            str(self.host),
            "--port",
            str(self.port),
            "--format",
            "plain",
            "--no-owner",
            "--no-privileges",
        ]

        if self.username:
            cmd.extend(["--username", self.username])

        cmd.append(self.database)
        return cmd

    def build_env(self) -> dict[str, str] | None:
        """Build environment variables for pg_dump.

        Returns:
            Environment dict with PGPASSWORD if password is set, else None
        """
        if self.password:
            return {"PGPASSWORD": self.password}
        return None


class DatabaseExportError(Exception):
    """Base exception for database export errors."""


class PgDumpNotFoundError(DatabaseExportError):
    """Raised when pg_dump command is not available."""


class PgDumpExecutionError(DatabaseExportError):
    """Raised when pg_dump execution fails."""

    def __init__(self, return_code: int, stderr: str):
        self.return_code = return_code
        self.stderr = stderr
        super().__init__(f"pg_dump failed with code {return_code}: {stderr}")


class DatabaseExportService:
    """Service for exporting PostgreSQL databases.

    This service handles the execution of pg_dump and streaming the output
    with gzip compression. It is designed to be testable by accepting
    configuration via dependency injection.

    Example:
        config = PgDumpConfig.from_url(db_url)
        service = DatabaseExportService(config)
        for chunk in service.export_gzipped():
            # write chunk to response
    """

    def __init__(self, config: PgDumpConfig):
        """Initialize the export service.

        Args:
            config: PgDump configuration
        """
        self.config = config

    @property
    def database_name(self) -> str:
        """Get the database name."""
        return self.config.database

    def generate_filename(self) -> str:
        """Generate export filename with timestamp.

        Returns:
            Filename in format: {database}_dump_{timestamp}.sql.gz
        """
        timestamp = datetime.now(tz=UTC).strftime("%Y%m%d_%H%M%S")
        return f"{self.config.database}_dump_{timestamp}.sql.gz"

    def export_gzipped(self, chunk_size: int = 8192) -> Iterator[bytes]:
        """Stream pg_dump output with gzip compression.

        Args:
            chunk_size: Size of chunks to read from pg_dump output

        Yields:
            Gzip-compressed chunks of the database dump

        Raises:
            PgDumpNotFoundError: If pg_dump is not installed
            PgDumpExecutionError: If pg_dump returns non-zero exit code
        """
        cmd = self.config.build_command()
        env = self.config.build_env()

        logger.info(f"Starting database export: {self.config.database}")

        # Create gzip compressor (wbits=16 + MAX_WBITS for gzip format)
        compressor = zlib.compressobj(wbits=zlib.MAX_WBITS | 16)

        try:
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env,
            )

            # Stream and compress stdout in chunks
            if process.stdout:
                for chunk in iter(lambda: process.stdout.read(chunk_size), b""):
                    compressed_chunk = compressor.compress(chunk)
                    if compressed_chunk:
                        yield compressed_chunk

            # Wait for process to complete
            return_code = process.wait()

            if return_code != 0:
                stderr = process.stderr.read() if process.stderr else b""
                error_msg = stderr.decode("utf-8", errors="replace")
                logger.error(f"pg_dump failed with code {return_code}: {error_msg}")
                raise PgDumpExecutionError(return_code, error_msg)

            # Flush remaining compressed data
            final_chunk = compressor.flush()
            if final_chunk:
                yield final_chunk

            logger.info(
                f"Database export completed successfully: {self.config.database}"
            )

        except FileNotFoundError as err:
            logger.error(
                "pg_dump command not found - PostgreSQL client tools not installed"
            )
            msg = "pg_dump not available - install PostgreSQL client tools"
            raise PgDumpNotFoundError(
                msg
            ) from err

    def export_raw(self, chunk_size: int = 8192) -> Iterator[bytes]:
        """Stream pg_dump output without compression.

        Useful for testing or when compression is not needed.

        Args:
            chunk_size: Size of chunks to read from pg_dump output

        Yields:
            Raw chunks of the database dump

        Raises:
            PgDumpNotFoundError: If pg_dump is not installed
            PgDumpExecutionError: If pg_dump returns non-zero exit code
        """
        cmd = self.config.build_command()
        env = self.config.build_env()

        try:
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env,
            )

            if process.stdout:
                yield from iter(lambda: process.stdout.read(chunk_size), b"")

            return_code = process.wait()

            if return_code != 0:
                stderr = process.stderr.read() if process.stderr else b""
                error_msg = stderr.decode("utf-8", errors="replace")
                raise PgDumpExecutionError(return_code, error_msg)

        except FileNotFoundError as err:
            msg = "pg_dump not available - install PostgreSQL client tools"
            raise PgDumpNotFoundError(
                msg
            ) from err


def is_postgresql_database(db_url: URL) -> bool:
    """Check if the database URL is for PostgreSQL.

    Args:
        db_url: SQLAlchemy database URL

    Returns:
        True if the database is PostgreSQL
    """
    return db_url.drivername.startswith("postgresql")
