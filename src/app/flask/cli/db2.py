# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from flask.cli import with_appcontext
from flask_super.cli import group
from rich import print

from app.flask.extensions import db

from . import util


@group(short_help="Additional database commands")
def db2() -> None:
    pass


@db2.command(short_help="Initialize database")
@with_appcontext
def initdb() -> None:
    db.create_all()
    print("Initialized the database")


@db2.command(short_help="Hot fixes for database")
@with_appcontext
def fix() -> None:
    print("Fixed the database")


@db2.command(short_help="Drop database")
@with_appcontext
def droptables() -> None:
    util.drop_tables()
    print("Dropped the database")

    util.inspect()


@db2.command()
@with_appcontext
def inspect() -> None:
    """Inspect the database schema."""
    util.inspect()
