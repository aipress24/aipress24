# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""give wall posts a date, a reference and images

Revision ID: c5e2a7b3d9f4
Revises: b4d1f6a2c8e3
Create Date: 2026-11-25 17:00:00

Wall posts already share a table which has `published_at`: the existing ones
are given their creation date.
"""

from __future__ import annotations

import sqlalchemy as sa
from advanced_alchemy.types.file_object import StoredObject
from alembic import op

# revision identifiers, used by Alembic.
revision = "c5e2a7b3d9f4"
down_revision = "b4d1f6a2c8e3"
branch_labels = None
depends_on = None

INDEX = "ix_frt_content_owner_external_ref"


def upgrade() -> None:
    op.add_column(
        "frt_content", sa.Column("external_ref", sa.String(500), nullable=True)
    )
    op.create_index(
        INDEX,
        "frt_content",
        ["owner_id", "external_ref"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
        sqlite_where=sa.text("deleted_at IS NULL"),
    )
    op.execute(
        "UPDATE frt_content SET published_at = created_at "
        "WHERE type = 'short_post' AND published_at IS NULL"
    )
    op.create_table(
        "soc_post_image",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("post_id", sa.BigInteger(), nullable=False),
        sa.Column("content", StoredObject(backend="s3"), nullable=True),
        sa.Column("caption", sa.String(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["post_id"], ["frt_content.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_soc_post_image_post_id", "soc_post_image", ["post_id"])


def downgrade() -> None:
    op.drop_table("soc_post_image")
    op.drop_index(INDEX, table_name="frt_content")
    op.drop_column("frt_content", "external_ref")
