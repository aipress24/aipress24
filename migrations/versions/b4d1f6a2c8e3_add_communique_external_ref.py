# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""add external_ref to crm_communique

Revision ID: b4d1f6a2c8e3
Revises: a3c9e5f1b7d2
Create Date: 2026-11-25 15:00:00

The reference an API client gives to the document a release comes from, so
that sending it again does not create a second release.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "b4d1f6a2c8e3"
down_revision = "a3c9e5f1b7d2"
branch_labels = None
depends_on = None

INDEX = "ix_crm_communique_owner_external_ref"


def upgrade() -> None:
    op.add_column(
        "crm_communique", sa.Column("external_ref", sa.String(500), nullable=True)
    )
    op.create_index(
        INDEX,
        "crm_communique",
        ["owner_id", "external_ref"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
        sqlite_where=sa.text("deleted_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index(INDEX, table_name="crm_communique")
    op.drop_column("crm_communique", "external_ref")
