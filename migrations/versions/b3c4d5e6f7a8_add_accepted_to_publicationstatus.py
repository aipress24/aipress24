# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""add ACCEPTED to publicationstatus enum

Revision ID: b3c4d5e6f7a8
Revises: e6f7a8b9c0d1
Create Date: 2026-09-23 14:30:00.000000

"""

from __future__ import annotations

from alembic import op

# revision identifiers, used by Alembic.
revision = "b3c4d5e6f7a8"
down_revision = "e6f7a8b9c0d1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("ALTER TYPE publicationstatus ADD VALUE IF NOT EXISTS 'ACCEPTED'")


def downgrade() -> None:
    pass
