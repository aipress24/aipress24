"""Admin views for database operations."""
# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

import subprocess
from collections.abc import Iterator
from datetime import UTC, datetime

from flask import Response, abort
from loguru import logger

from app.flask.extensions import db

from . import blueprint


@blueprint.route("/export-db/")
def export_database():
    """Export PostgreSQL database using pg_dump.

    Returns a downloadable .sql file containing the full database dump.
    Only accessible to users with ADMIN role (enforced by blueprint.before_request).

    Returns:
        Response: Streaming response with pg_dump output

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

    # Extract connection parameters
    host = db_url.host or "localhost"
    port = db_url.port or 5432
    database = db_url.database
    username = db_url.username
    password = db_url.password

    if not database:
        logger.error("No database name found in database URL")
        abort(500, "Database configuration error")

    # Build pg_dump command
    # fmt: off
    cmd = [
        "pg_dump",
        "--host", str(host),
        "--port", str(port),
        "--format", "plain",  # SQL format
        "--no-owner",  # Don't output ownership commands
        "--no-privileges",  # Don't output privilege commands
    ]
    # fmt: on

    # Add username if provided
    if username:
        cmd.extend(["--username", username])

    # Add database name
    cmd.append(database)

    # Set environment for password
    env = None
    if password:
        env = {"PGPASSWORD": password}

    # Generate filename with timestamp
    timestamp = datetime.now(tz=UTC).strftime("%Y%m%d_%H%M%S")
    filename = f"{database}_dump_{timestamp}.sql"

    logger.info(f"Starting database export: {database} -> {filename}")

    def generate() -> Iterator[bytes]:
        """Stream pg_dump output."""
        try:
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env,
            )

            # Stream stdout in chunks
            if process.stdout:
                yield from iter(lambda: process.stdout.read(8192), b"")

            # Wait for process to complete
            return_code = process.wait()

            if return_code != 0:
                stderr = process.stderr.read() if process.stderr else b""
                error_msg = stderr.decode("utf-8", errors="replace")
                logger.error(f"pg_dump failed with code {return_code}: {error_msg}")
                msg = f"pg_dump failed: {error_msg}"
                raise RuntimeError(msg)

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
        mimetype="application/sql",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "X-Content-Type-Options": "nosniff",
        },
    )
