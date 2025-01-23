# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from flask.cli import with_appcontext
from flask_super.cli import group
from rich import print
from sqlalchemy import text

from app.flask.extensions import db

from . import db_util


@group(short_help="Additional database commands")
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
