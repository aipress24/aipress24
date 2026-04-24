"""add cms_corporate_page

Revision ID: a65e652eab6b
Revises: e5b2a97f3c14
Create Date: 2026-04-24 17:30:09.932161

Creates the `cms_corporate_page` table backing the mini-CMS for
legal / marketing pages (CGV, confidentialité, « Notre offre »,
etc.). Spec: `local-notes/specs/corporate-pages-cms.md`.
"""
from __future__ import annotations

import sqlalchemy as sa
import sqlalchemy_utils
from alembic import op

revision = "a65e652eab6b"
down_revision = "e5b2a97f3c14"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "cms_corporate_page",
        sa.Column("slug", sa.String(), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("body_md", sa.Text(), nullable=False),
        sa.Column("updated_by_id", sa.Integer(), nullable=True),
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column(
            "timestamp",
            sqlalchemy_utils.types.arrow.ArrowType(timezone=True),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["updated_by_id"], ["aut_user.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_cms_corporate_page_slug",
        "cms_corporate_page",
        ["slug"],
        unique=True,
    )


def downgrade():
    op.drop_index("ix_cms_corporate_page_slug", table_name="cms_corporate_page")
    op.drop_table("cms_corporate_page")
