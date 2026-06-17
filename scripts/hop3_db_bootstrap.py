#!/usr/bin/env python
"""Bring the AIPress24 database to head — works on an empty OR a populated DB.

Run by scripts/hop3-before-run.sh, from the repo root (where etc/settings.toml
and migrations/ live), with DATABASE_URL injected by the postgres addon.

Why not a plain `flask db upgrade`: AIPress24's Alembic chain cannot be replayed
from empty. The `recreate_baseline_for_existing_database` migration assumes the
core tables (aut_user, ...) already exist — they were originally created by
db.create_all(), not by a migration — so the next migration fails with
`relation "aut_user" does not exist`. Therefore:

  - Empty DB (no tables, no alembic_version): build the schema from the models
    (db.create_all) and stamp Alembic at head.
  - Existing, Alembic-managed DB (alembic_version present — e.g. a restored
    production dump): run the migrations (`flask db upgrade`).
  - Tables but no alembic_version: refuse (unmanaged schema of unknown origin).
"""

from __future__ import annotations

import sys

from flask_migrate import stamp, upgrade
from sqlalchemy import inspect

from app.flask.extensions import db
from app.flask.main import create_app

ALEMBIC_VERSION_TABLE = "alembic_version"


def main() -> int:
    app = create_app()
    with app.app_context():
        tables = inspect(db.engine).get_table_names()
        has_alembic = ALEMBIC_VERSION_TABLE in tables
        app_tables = [t for t in tables if t != ALEMBIC_VERSION_TABLE]

        if not app_tables and not has_alembic:
            print("[db-bootstrap] empty database: create_all + stamp head")
            db.create_all()
            stamp(revision="head")
        elif has_alembic:
            print("[db-bootstrap] alembic-managed database: db upgrade")
            upgrade()
        else:
            print(
                "[db-bootstrap] ERROR: tables exist but no alembic_version — "
                "refusing to touch an unmanaged schema.",
                file=sys.stderr,
            )
            return 1

    print("[db-bootstrap] done")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
