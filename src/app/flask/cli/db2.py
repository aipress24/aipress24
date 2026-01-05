# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

import shutil
import subprocess
import sys
from urllib.parse import urlparse

import click
from devtools import debug
from flask import current_app
from flask.cli import with_appcontext
from flask_super.cli import group
from rich import print
from sqlalchemy import text
from tenacity import retry, stop_after_attempt, wait_exponential

from app.flask.extensions import db

from . import db_util


@group(short_help="Extra database commands")
def db2() -> None:
    pass


@db2.command(short_help="Initialize database")
@with_appcontext
def create() -> None:
    db.create_all()
    print("Initialized the database")


@db2.command(short_help="Hot fixes for database")
@with_appcontext
def fix() -> None:
    print("Fixed the database")


@db2.command(short_help="Drop database")
@with_appcontext
def drop() -> None:
    try:
        with db.session.begin():
            db.session.execute(text("DROP SCHEMA public CASCADE;"))
            db.session.execute(text("CREATE SCHEMA public;"))
        print("Schema 'public' recreated successfully.")
    except Exception as e:
        print(f"Error: {e}")
        db.session.rollback()


@db2.command()
@with_appcontext
def inspect() -> None:
    """Inspect the database schema."""
    db_util.show_tables()


@db2.command()
def upgrade() -> None:
    """Run database migration."""
    _upgrade()


@retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=1, max=10),
)
def _upgrade() -> None:
    flask = sys.argv[0]
    subprocess.run([flask, "db", "upgrade"], check=True)


@db2.command()
@click.argument("filename")
@with_appcontext
def import_sql(filename: str) -> None:
    """Import SQL file."""

    sqlalchemy_url = current_app.config["SQLALCHEMY_DATABASE_URI"]

    parsed_url = urlparse(sqlalchemy_url)
    hostname = parsed_url.hostname
    port = parsed_url.port
    database = parsed_url.path.lstrip("/")
    username = parsed_url.username
    password = parsed_url.password
    env = {
        "PGHOST": hostname,
        "PGPORT": str(port),
        "PGDATABASE": database,
    }
    if password:
        env["PGPASSWORD"] = password
    if username:
        env["PGUSER"] = username
    debug(env)

    pg_restore = shutil.which("pg_restore")
    if not pg_restore:
        print("Error: pg_restore not found in PATH")
        return
    cmd = [pg_restore, "-d", database, filename]
    print(" ".join(cmd))
    subprocess.run(cmd, env=env, check=True)
