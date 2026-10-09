# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""add DECLINE to statutavis enum

Revision ID: e7a1b2c3d4f5
Revises: 3b8f37dfacf2
Create Date: 2026-10-09 15:00:00.000000

"""

from __future__ import annotations

from alembic import op

# revision identifiers, used by Alembic.
revision = "e7a1b2c3d4f5"
down_revision = "3b8f37dfacf2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("ALTER TYPE statutavis ADD VALUE IF NOT EXISTS 'DECLINE'")
        op.execute("ALTER TYPE statutavis ADD VALUE IF NOT EXISTS 'decline'")


def downgrade() -> None:
    pass
