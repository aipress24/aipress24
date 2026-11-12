# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""remove sign-up passwords stored in clear in ses_session

Revision ID: a3c9e5f1b7d2
Revises: 52b861396d51
Create Date: 2026-11-12 10:00:00

The sign-up wizard kept the typed password in `ses_session._data`. A
finished sign-up no longer needs it, so it is dropped; an unfinished one
gets the hash the wizard now stores in its place.
"""

from __future__ import annotations

import json
from collections.abc import Callable

import sqlalchemy as sa
from alembic import op
from flask_security import hash_password

# revision identifiers, used by Alembic.
revision = "a3c9e5f1b7d2"
down_revision = "52b861396d51"
branch_labels = None
depends_on = None

#: `app.modules.kyc.views.SESSION_HASH_KEY`, frozen here.
HASH_KEY = "password_hash"


def upgrade() -> None:
    conn = op.get_bind()
    emails = {
        email.strip().lower()
        for (email,) in conn.execute(sa.text("SELECT email FROM aut_user"))
        if email
    }
    rows = conn.execute(
        sa.text("SELECT id, _data FROM ses_session WHERE _data LIKE '%password%'")
    ).all()
    for row_id, raw in rows:
        data = scrub(json.loads(raw), emails, hash_password)
        conn.execute(
            sa.text("UPDATE ses_session SET _data = :data WHERE id = :id"),
            {"data": json.dumps(data), "id": row_id},
        )


def downgrade() -> None:
    """Nothing to restore: the passwords are gone by design."""


def scrub(data: dict, user_emails: set[str], hasher: Callable[[str], str]) -> dict:
    """Return `data` with no password in clear.

    The wizard stores its answers under `form_raw_results`; `password`
    there is the only place a typed password sits.
    """
    answers = data.get("form_raw_results")
    if not isinstance(answers, dict) or "password" not in answers:
        return data
    answers = dict(answers)
    password = str(answers.pop("password") or "").strip()
    email = str(answers.get("email") or "").strip().lower()
    if password and email not in user_emails:
        answers[HASH_KEY] = hasher(password)
    return {**data, "form_raw_results": answers}
