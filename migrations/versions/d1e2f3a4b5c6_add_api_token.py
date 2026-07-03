"""add api_token table for the public API

Revision ID: d1e2f3a4b5c6
Revises: c2d3e4f5a6b7
Create Date: 2025-07-03 00:00:00.000000

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "d1e2f3a4b5c6"
down_revision = "c2d3e4f5a6b7"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "api_token",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("token_prefix", sa.String(length=16), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("scopes", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["aut_user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_api_token_token_hash", "api_token", ["token_hash"], unique=True
    )
    op.create_index("ix_api_token_user_id", "api_token", ["user_id"], unique=False)


def downgrade():
    op.drop_index("ix_api_token_user_id", table_name="api_token")
    op.drop_index("ix_api_token_token_hash", table_name="api_token")
    op.drop_table("api_token")
