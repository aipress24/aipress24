# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only
"""Script to remove all Business Walls and associated data.

Usage: uv run --env-file .env scripts/remove_all_bw.py
"""

from __future__ import annotations

from sqlalchemy import update

from app.flask.extensions import db
from app.flask.main import create_app
from app.models.auth import User
from app.models.organisation import Organisation
from app.modules.bw.bw_activation.models import BusinessWall


def remove_all_bw():
    db_session = db.session

    print("Researching Business Walls to remove...")
    bw_count = db_session.query(BusinessWall).count()
    if bw_count == 0:
        print("No Business Wall records found. Nothing to do.")
        return

    print(f"Found {bw_count} Business Wall records.")

    # 1. Update all Users: clear selected_bw_id
    print("Clearing selected_bw_id for all users...")
    db_session.execute(update(User).values(selected_bw_id=None))

    # 2. Update all Organisations: clear BW-related fields
    print("Clearing BW fields for all organisations...")
    db_session.execute(
        update(Organisation).values(
            bw_id=None,
            bw_active=None,
            bw_name="",
        )
    )

    # 3. Delete all BusinessWall records
    # Associated data (Subscription, BWContent, RoleAssignment, Partnership, BWImage)
    # will be deleted by database-level cascade.
    print(f"Deleting {bw_count} BusinessWall records and their associated data...")
    db_session.query(BusinessWall).delete()

    print("Committing changes...")
    db_session.commit()
    print("Cleanup complete.")


if __name__ == "__main__":
    app = create_app()
    with app.app_context():
        remove_all_bw()
