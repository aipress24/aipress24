"""Admin views for database operations."""
# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

import subprocess
import zlib
from collections.abc import Iterator
from datetime import UTC, datetime

from flask import Response, abort
from loguru import logger

from app.flask.extensions import db

from . import blueprint


def _build_pg_dump_command(db_url) -> tuple[list[str], dict[str, str] | None]:
    """Build pg_dump command and environment from database URL.

    Args:
        db_url: SQLAlchemy database URL

    Returns:
        Tuple of (command list, environment dict or None)

    Raises:
        ValueError: If database configuration is invalid
    """
    # Extract connection parameters
    host = db_url.host or "localhost"
    port = db_url.port or 5432
    database = db_url.database
    username = db_url.username
    password = db_url.password

    if not database:
        msg = "No database name found in database URL"
        raise ValueError(msg)

    # Build pg_dump command
    cmd = [
        "pg_dump",
        "--host",
        str(host),
        "--port",
        str(port),
        "--format",
        "plain",
        "--no-owner",
        "--no-privileges",
    ]

    # Add username if provided
    if username:
        cmd.extend(["--username", username])

    # Add database name
    cmd.append(database)

    # Set environment for password
    env = None
    if password:
        env = {"PGPASSWORD": password}

    return cmd, env


@blueprint.route("/export-db/")
def export_database():
    """Export PostgreSQL database using pg_dump.

    Returns a downloadable .sql.gz file containing the gzipped database dump.
    Only accessible to users with ADMIN role (enforced by blueprint.before_request).

    Returns:
        Response: Streaming response with gzip-compressed pg_dump output

    Raises:
        404: If database is not PostgreSQL
        500: If pg_dump fails
    """
    # Get database URL from SQLAlchemy engine
    db_url = db.engine.url

    # Only support PostgreSQL
    if not db_url.drivername.startswith("postgresql"):
        logger.error(
            f"Database export only supports PostgreSQL, got: {db_url.drivername}"
        )
        abort(404, "Database export only available for PostgreSQL databases")

    # Build pg_dump command and environment
    try:
        cmd, env = _build_pg_dump_command(db_url)
    except ValueError as e:
        logger.error(str(e))
        abort(500, "Database configuration error")

    database = db_url.database

    # Generate filename with timestamp
    timestamp = datetime.now(tz=UTC).strftime("%Y%m%d_%H%M%S")
    filename = f"{database}_dump_{timestamp}.sql.gz"

    logger.info(f"Starting database export: {database} -> {filename}")

    def generate() -> Iterator[bytes]:
        """Stream pg_dump output with gzip compression."""
        # Create gzip compressor (wbits=16 + zlib.MAX_WBITS for gzip format)
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
                for chunk in iter(lambda: process.stdout.read(8192), b""):
                    compressed_chunk = compressor.compress(chunk)
                    if compressed_chunk:
                        yield compressed_chunk

            # Wait for process to complete
            return_code = process.wait()

            if return_code != 0:
                stderr = process.stderr.read() if process.stderr else b""
                error_msg = stderr.decode("utf-8", errors="replace")
                logger.error(f"pg_dump failed with code {return_code}: {error_msg}")
                msg = f"pg_dump failed: {error_msg}"
                raise RuntimeError(msg)

            # Flush remaining compressed data
            final_chunk = compressor.flush()
            if final_chunk:
                yield final_chunk

            logger.info(f"Database export completed successfully: {filename}")

        except FileNotFoundError as err:
            logger.error(
                "pg_dump command not found - PostgreSQL client tools not installed"
            )
            msg = "pg_dump not available - install PostgreSQL client tools"
            raise RuntimeError(msg) from err
        except Exception as e:
            logger.error(f"Database export failed: {e}")
            raise

    return Response(
        generate(),
        mimetype="application/gzip",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "X-Content-Type-Options": "nosniff",
        },
    )
