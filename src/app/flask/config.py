# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

import os

from dynaconf import Dynaconf
from flask import Flask
from flask_super.initializers.logging import init_sentry
from jinja2 import StrictUndefined

__all__ = ["setup_config"]

from loguru import logger


def setup_config(app, config) -> None:
    configure_app(app, config)
    app.jinja_env.undefined = StrictUndefined
    # Configure logging as soon as we have the config
    init_logging(app)


def init_logging(app: Flask) -> None:
    run_from_cli = app.config.get("RUN_FROM_CLI")
    if run_from_cli and not app.debug:
        # Disable logging output in CLI mode
        logger.configure(handlers=[])
    else:
        init_sentry(app)


def configure_app(app, config) -> None:
    if config:
        # Probably testing -> use dedicated config object
        app.config.from_object(config)

    else:
        dynaconf = Dynaconf(
            settings_files=["etc/settings.toml", "etc/secrets.toml"],
            environments=True,
            envvar_prefix="FLASK",
        )
        app.config.from_mapping(dynaconf)

    set_db_uri(app)


def set_db_uri(app: Flask) -> None:
    """Get the SQLAlchemy database URI from the environment or config."""
    database_url = get_db_url(app)
    if database_url:
        app.config["SQLALCHEMY_DATABASE_URI"] = database_url

    redis_url = os.environ.get("REDISCLOUD_URL", "")
    if redis_url:
        app.config["REDIS_URL"] = redis_url


def get_db_url(app):
    # Heroku
    database_url = os.environ.get("DATABASE_URL", "")
    # Clever Cloud
    if not database_url:
        database_url = os.environ.get("POSTGRESQL_ADDON_URI", "")
    # if not database_url and app.config.get("DB"):
    #     database_url = app.config["DB"]["URI"]
    if database_url.startswith("postgres:"):
        database_url = database_url.replace("postgres:", "postgresql:")
    return database_url


def dump_config(app: Flask) -> None:
    config_ = dict(sorted(app.config.items()))
    print("CONFIG:")
    for k, v in config_.items():
        print(f"{k}: {v}")
    print()

    print("ENV:")
    env_ = dict(sorted(os.environ.items()))
    for k, v in env_.items():
        print(f"{k}: {v}")
