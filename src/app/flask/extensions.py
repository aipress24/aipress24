"""Flask extensions setup and initialization."""
# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

import fsspec
from advanced_alchemy.base import UUIDAuditBase
from advanced_alchemy.types.file_object import storages
from advanced_alchemy.types.file_object.backends.fsspec import FSSpecBackend
from flask import Flask
from flask_babel import Babel
from flask_htmx import HTMX
from flask_mailman import Mail
from flask_migrate import Migrate
from flask_security import Security, SQLAlchemySessionUserDatastore
from flask_sqlalchemy import SQLAlchemy
from flask_talisman import DEFAULT_CSP_POLICY, Talisman
from flask_vite import Vite
from loguru import logger
from pytz import timezone

from app.models.auth import Role, User
from app.models.base import Base

PARIS_TZ = timezone("Europe/Paris")

# Merge existing Base tables into UUIDAuditBase metadata
# This allows both bases to coexist and be detected by Alembic
for table in Base.metadata.tables.values():
    table.to_metadata(UUIDAuditBase.metadata)

# Create all extensions as global variables
db = SQLAlchemy(
    model_class=Base,
    metadata=UUIDAuditBase.metadata,
)
migrate = Migrate()

# Alternative to Flask-SQLAlchemy. Not sure if it's better.
# db = Alchemical(model_class=Base)

mail = Mail()
vite = Vite()
babel = Babel(default_locale="fr", default_timezone=PARIS_TZ)
# wakaq = WakaQ()
# session = Session()

security = Security()

htmx = HTMX()


# # Define models
# fsqla.FsModels.set_db_info(db)


def register_extensions(app: Flask) -> None:
    """Register all Flask extensions.

    Args:
        app: Flask application instance.
    """
    logger.debug("Registering all extensions")

    db.init_app(app)
    # register_local_storage(app)
    register_s3_storage(app)

    mail.init_app(app)
    babel.init_app(app)
    migrate.init_app(app, db)
    vite.init_app(app)
    # rq.init_app(app)
    # wakaq.init_app(app)
    setup_security(app, db)
    htmx.init_app(app)

    if app.debug:
        setup_debug_toolbar(app)

    if not app.debug and not app.testing:
        csp = app.config.get("CONTENT_SECURITY_POLICY", DEFAULT_CSP_POLICY)
        Talisman(app, content_security_policy=csp, force_https=False)


def register_s3_storage(app: Flask) -> None:
    endpoint_url = app.config["S3_ENDPOINT_URL"]
    access_key = app.config["S3_ACCESS_KEY_ID"]
    secret_key = app.config["S3_SECRET_ACCESS_KEY"]
    bucket_name = app.config["S3_BUCKET_NAME"]
    use_ssl = app.config.get("S3_USE_SSL", False)

    s3_fs = fsspec.filesystem(
        "s3",
        client_kwargs={
            "endpoint_url": endpoint_url,
            "aws_access_key_id": access_key,
            "aws_secret_access_key": secret_key,
            "verify": use_ssl,
        },
        use_ssl=use_ssl,
    )
    prefix = f"{bucket_name}/files"
    storages.register_backend(FSSpecBackend(fs=s3_fs, key="s3", prefix=prefix))


def register_local_storage(app: Flask) -> None:
    # Path(app.config["STORAGE_ROOT"]).mkdir(parents=True, exist_ok=True)
    local_fs = fsspec.filesystem("file")
    storages.register_backend(
        FSSpecBackend(fs=local_fs, key="local", prefix=app.config["STORAGE_ROOT"])
    )


def setup_debug_toolbar(app: Flask) -> None:
    """Setup Flask debug toolbar for development.

    Args:
        app: Flask application instance.
    """
    from flask_debugtoolbar import DebugToolbarExtension

    DebugToolbarExtension(app)


def setup_security(app: Flask, db: SQLAlchemy) -> None:
    """Setup Flask-Security."""

    user_datastore = SQLAlchemySessionUserDatastore(db.session, User, Role)
    security.init_app(app, user_datastore)
