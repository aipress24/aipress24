# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Admin views for database operations."""

from __future__ import annotations

from typing import TYPE_CHECKING

from flask import Response, abort
from loguru import logger

from app.flask.extensions import db

from . import blueprint
from .db_export_service import (
    DatabaseExportError,
    DatabaseExportService,
    PgDumpConfig,
    is_postgresql_database,
)

if TYPE_CHECKING:
    from sqlalchemy.engine import URL


# Service factory - can be replaced in tests
_service_factory: type[DatabaseExportService] = DatabaseExportService


def set_service_factory(factory: type[DatabaseExportService]) -> None:
    """Set the service factory for dependency injection (used in tests)."""
    global _service_factory
    _service_factory = factory


def reset_service_factory() -> None:
    """Reset service factory to default (used in tests)."""
    global _service_factory
    _service_factory = DatabaseExportService


def create_export_response(
    db_url: URL,
    service_class: type[DatabaseExportService] = DatabaseExportService,
) -> Response:
    """Create export response from database URL.

    This function contains the core logic for database export, separated from
    the route handler for testability.

    Args:
        db_url: SQLAlchemy database URL
        service_class: Service class to use (for dependency injection)

    Returns:
        Flask Response with streaming gzipped database dump

    Raises:
        404: If database is not PostgreSQL
        500: If database configuration is invalid
    """
    if not is_postgresql_database(db_url):
        logger.error(
            f"Database export only supports PostgreSQL, got: {db_url.drivername}"
        )
        abort(404, "Database export only available for PostgreSQL databases")

    try:
        config = PgDumpConfig.from_url(db_url)
    except ValueError as e:
        logger.error(str(e))
        abort(500, "Database configuration error")

    service = service_class(config)
    filename = service.generate_filename()

    logger.info(f"Starting database export: {service.database_name} -> {filename}")

    def generate_with_error_handling():
        """Wrap service generator with error handling."""
        try:
            yield from service.export_gzipped()
        except DatabaseExportError as e:
            logger.error(f"Database export failed: {e}")
            raise

    return Response(
        generate_with_error_handling(),
        mimetype="application/gzip",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "X-Content-Type-Options": "nosniff",
        },
    )


@blueprint.route("/export-db/")
def export_database():
    """Export PostgreSQL database using pg_dump.

    Returns a downloadable .sql.gz file containing the gzipped database dump.
    Only accessible to users with ADMIN role (enforced by blueprint.before_request).

    Returns:
        Response: Streaming response with gzip-compressed pg_dump output

    Raises:
        404: If database is not PostgreSQL
        500: If pg_dump fails or database configuration is invalid
    """
    return create_export_response(db.engine.url, _service_factory)
