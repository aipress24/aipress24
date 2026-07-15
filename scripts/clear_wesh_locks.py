# Copyright (c) 2025, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

# ruff: noqa: INP001

"""Clear wesh search-index locks from the database and rebuild it.

Usage:
    psql -d aipress24 -c "DELETE FROM dramatiq.queue;"
    uv run --env-file .env scripts/clear_wesh_locks.py
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Make `from app...` imports work when the script is run standalone
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

# Make `from app...` imports work when the script is run standalone
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

os.environ.setdefault("AIPRESS_SKIP_DRAMATIQ", "1")

from flask_security import hash_password  # noqa: E402
from sqlalchemy import select  # noqa: E402

from app.flask.extensions import db  # noqa: E402
from app.flask.main import create_app  # noqa: E402
from app.models.auth import User  # noqa: E402

from sqlalchemy import text  # noqa: E402

from app.flask.extensions import db  # noqa: E402
from app.flask.main import create_app  # noqa: E402


def _db_url() -> str:
    url = os.environ.get("FLASK_SQLALCHEMY_DATABASE_URI")
    if not url:
        raise RuntimeError(msg)
    return url


def clear_wesh_locks(*, drop_tables: bool = False) -> int:
    app = create_app()
    operation = "DROP TABLE" if drop_tables else "DELETE FROM"
    count = 0

    with app.app_context():
        engine = db.engine
        with engine.begin() as conn:
            table_names = (
                conn.execute(
                    text(
                        "SELECT table_name FROM information_schema.tables "
                        "WHERE table_schema = 'public' AND table_name LIKE 'wesh_%'"
                    )
                )
                .scalars()
                .all()
            )

            for table_name in table_names:
                suffix = " CASCADE" if drop_tables else ""
                conn.execute(text(f"{operation} {table_name}{suffix}"))
                count += 1
                print(f"  {operation} {table_name}")

    return count


def rebuild_search_index() -> None:
    """Run ``flask search rebuild`` programmatically."""
    app = create_app()
    with app.app_context():
        from app.modules.search.cli import rebuild_index  # noqa: PLC0415

        rebuild_index(show_progress=False)
        print("Search index rebuilt.")


def main() -> int:

    count = clear_wesh_locks()
    print(f"Done ({count} table(s) affected).")

    print("Rebuilding search index...")
    rebuild_search_index()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
