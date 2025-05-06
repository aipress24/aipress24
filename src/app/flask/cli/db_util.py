# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

import sys

import sqlalchemy as sa
from cleez.colors import blue, dim, error
from sqlalchemy import Inspector, MetaData, Table
from sqlalchemy.sql.ddl import DropConstraint, DropTable

from app.flask.extensions import db


def drop_tables() -> None:
    print("Dropping tables...")
    drop_everything()
    print("... done")

    ins = sa.inspect(db.engine)
    if len(ins.get_table_names()) > 0:
        print(error("Database is not empty:"))
        sys.exit(1)


def drop_everything() -> None:
    # https://github.com/pallets-eco/flask-sqlalchemy/issues/722#issuecomment-705672929
    """(On a live db) drops all foreign key constraints before dropping all
    tables.

    Workaround for SQLAlchemy not doing DROP ## CASCADE for drop_all()
    (https://github.com/pallets/flask-sqlalchemy/issues/722)
    """
    con = db.engine.connect()
    # transaction = con.begin()
    with con.begin():
        inspector = Inspector.from_engine(db.engine)

        # We need to re-create a minimal metadata with only the required things to
        # successfully emit drop constraints and tables commands for postgres (based
        # on the actual schema of the running instance)
        meta = MetaData()
        tables = []
        all_fkeys = []

        for table_name in inspector.get_table_names():
            fkeys = []

            for fkey in inspector.get_foreign_keys(table_name):
                if not fkey["name"]:
                    continue

                fkeys.append(db.ForeignKeyConstraint((), (), name=fkey["name"]))

            tables.append(Table(table_name, meta, *fkeys))
            all_fkeys.extend(fkeys)

        for fkey in all_fkeys:
            con.execute(DropConstraint(fkey))

        for table in tables:
            con.execute(DropTable(table))

    # transaction.commit()


def show_tables() -> None:
    ins = sa.inspect(db.engine)

    table_names = sorted(ins.get_table_names())
    if not table_names:
        print(blue("No tables found"))
        return

    print(blue("Table list:"))

    for _t in table_names:
        print(dim(_t))
