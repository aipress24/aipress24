# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Seed the dev DB with the test profiles listed in the project CSV.

Imports `local-notes/cards/attachments/00-ListeDesProfilsDeTests-7.2.csv`
into the local database — minimal `User` + community `Role` per row.
Just enough for the e2e_playwright suite to run against
`http://127.0.0.1:5000`.

Usage :

    flask seed-test-profiles                # additive
    flask seed-test-profiles --update       # also reset password to CSV value
    flask seed-test-profiles --limit 5      # subset for a quick smoke

Idempotent : existing users (by email) are kept by default ; with
`--update` their password is reset to the CSV value (useful when
the CSV rotates).
"""

from __future__ import annotations

import csv
import re
from pathlib import Path

import click
from flask.cli import with_appcontext
from flask_security import hash_password
from flask_super.cli import command

from app.enums import CommunityEnum
from app.flask.extensions import db
from app.models.auth import KYCProfile, Role, User
from app.modules.kyc.community_role import (
    COMMUNITY_TO_ROLE,
    set_user_role_from_community,
)

CSV_PATH = (
    Path(__file__).resolve().parent.parent.parent.parent.parent
    / "local-notes" / "cards" / "attachments"
    / "00-ListeDesProfilsDeTests-7.2.csv"
)
CATEGORY_RE = re.compile(
    r"^(Journalistes|PR Agency|Academics|Transformers|Leaders & Experts)"
)
SECTION_TO_COMMUNITY = {
    "Journalistes": CommunityEnum.PRESS_MEDIA,
    "PR Agency": CommunityEnum.COMMUNICANTS,
    "Leaders & Experts": CommunityEnum.LEADERS_EXPERTS,
    "Transformers": CommunityEnum.TRANSFORMERS,
    "Academics": CommunityEnum.ACADEMICS,
}


def _parse_csv() -> list[dict]:
    rows: list[dict] = []
    section = "?"
    with CSV_PATH.open(encoding="utf-8") as f:
        for row in csv.reader(f):
            if not row:
                continue
            first = row[0].strip()
            m = CATEGORY_RE.match(first)
            if m:
                section = m.group(1)
                continue
            if first == "Prénom" or len(row) < 6:
                continue
            prenom, nom, _fonction, _org, mail = (
                c.strip() for c in row[:5]
            )
            pw = row[5]  # raw — leading space matters for one account
            if not mail or "@" not in mail:
                continue
            community = SECTION_TO_COMMUNITY.get(section)
            if community is None:
                continue
            rows.append(
                {
                    "first_name": prenom,
                    "last_name": nom,
                    "email": mail,
                    "password": pw,
                    "community": community,
                }
            )
    return rows


def _ensure_role_map() -> dict[str, Role]:
    """Create any missing community Role rows and return a name → Role
    map suitable for `set_user_role_from_community`."""
    needed = {role.name for role in COMMUNITY_TO_ROLE.values()}
    role_map: dict[str, Role] = {}
    for name in needed:
        role = db.session.query(Role).filter_by(name=name).first()
        if role is None:
            role = Role(name=name, description=name.lower())
            db.session.add(role)
            db.session.flush()
        role_map[name] = role
    return role_map


@command(name="seed-test-profiles", short_help="Import the test-profile CSV.")
@click.option(
    "--update",
    is_flag=True,
    default=False,
    help="Reset the password on already-existing accounts.",
)
@click.option(
    "--limit",
    type=int,
    default=0,
    help="Stop after N rows (0 = no limit).",
)
@with_appcontext
def seed_test_profiles(update: bool, limit: int) -> None:
    """Import the test-profile CSV into the local DB."""
    rows = _parse_csv()
    if limit:
        rows = rows[:limit]

    role_map = _ensure_role_map()

    created = 0
    updated = 0
    skipped = 0
    for row in rows:
        existing = db.session.query(User).filter_by(email=row["email"]).first()
        if existing is None:
            user = User(
                email=row["email"],
                first_name=row["first_name"],
                last_name=row["last_name"],
                active=True,
                password=hash_password(row["password"]),
            )
            db.session.add(user)
            db.session.flush()

            # Minimal KYCProfile so legacy code that touches
            # `user.profile` doesn't trip.
            profile = KYCProfile(user_id=user.id)
            db.session.add(profile)
            db.session.flush()

            set_user_role_from_community(role_map, user, row["community"])
            click.echo(f"  + {row['email']}  ({row['community'].name})")
            created += 1
        elif update:
            existing.password = hash_password(row["password"])
            set_user_role_from_community(role_map, existing, row["community"])
            click.echo(f"  ~ {row['email']}  (password + role updated)")
            updated += 1
        else:
            skipped += 1

    db.session.commit()
    click.echo(
        f"\nDone. created={created}, updated={updated}, skipped={skipped}"
    )
