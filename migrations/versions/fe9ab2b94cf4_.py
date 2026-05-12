"""Rename profileenum + tighten marketplace + stripe_price column types

Manually edited after autogenerate produced:

- 17 DROP TABLE statements for wesh/whoosh-managed tables in the
  ``public`` schema. Those tables are managed out-of-band by wesh
  (re-created at app boot) and must NOT be touched by alembic.
  Filtered out in ``env.py`` via ``include_object`` so future
  autogenerate runs don't propose them either.

- An ``ALTER COLUMN profile TYPE profileenum`` that pointed at a type
  that doesn't exist yet. The actual schema change wanted is a *type
  rename*: ``ALTER TYPE adm_profileenum RENAME TO profileenum``.
  Replaced below.

Revision ID: fe9ab2b94cf4
Revises: 4140cfd1faba
Create Date: 2026-05-12 19:44:01.683370
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "fe9ab2b94cf4"
down_revision = "4140cfd1faba"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Rename the existing enum type. PG metadata-only operation; every
    # column already bound to ``adm_profileenum`` keeps its binding
    # under the new name, so we don't need an ``ALTER TABLE``.
    op.execute("ALTER TYPE adm_profileenum RENAME TO profileenum")

    with op.batch_alter_table("mkp_job_offer", schema=None) as batch_op:
        batch_op.alter_column(
            "pays_zip_ville",
            existing_type=sa.VARCHAR(),
            nullable=False,
            existing_server_default=sa.text("''::character varying"),
        )
        batch_op.alter_column(
            "pays_zip_ville_detail",
            existing_type=sa.VARCHAR(),
            nullable=False,
            existing_server_default=sa.text("''::character varying"),
        )

    with op.batch_alter_table("mkp_mission_offer", schema=None) as batch_op:
        batch_op.alter_column(
            "pays_zip_ville",
            existing_type=sa.VARCHAR(),
            nullable=False,
            existing_server_default=sa.text("''::character varying"),
        )
        batch_op.alter_column(
            "pays_zip_ville_detail",
            existing_type=sa.VARCHAR(),
            nullable=False,
            existing_server_default=sa.text("''::character varying"),
        )

    with op.batch_alter_table("mkp_project_offer", schema=None) as batch_op:
        batch_op.alter_column(
            "pays_zip_ville",
            existing_type=sa.VARCHAR(),
            nullable=False,
            existing_server_default=sa.text("''::character varying"),
        )
        batch_op.alter_column(
            "pays_zip_ville_detail",
            existing_type=sa.VARCHAR(),
            nullable=False,
            existing_server_default=sa.text("''::character varying"),
        )

    with op.batch_alter_table("stripe_price", schema=None) as batch_op:
        batch_op.alter_column(
            "unit_amount_cents",
            existing_type=sa.BIGINT(),
            type_=sa.Integer(),
            existing_nullable=False,
        )
        batch_op.alter_column(
            "synced_at",
            existing_type=postgresql.TIMESTAMP(timezone=True),
            type_=sa.DateTime(),
            existing_nullable=False,
            existing_server_default=sa.text("now()"),
        )


def downgrade() -> None:
    with op.batch_alter_table("stripe_price", schema=None) as batch_op:
        batch_op.alter_column(
            "synced_at",
            existing_type=sa.DateTime(),
            type_=postgresql.TIMESTAMP(timezone=True),
            existing_nullable=False,
            existing_server_default=sa.text("now()"),
        )
        batch_op.alter_column(
            "unit_amount_cents",
            existing_type=sa.Integer(),
            type_=sa.BIGINT(),
            existing_nullable=False,
        )

    with op.batch_alter_table("mkp_project_offer", schema=None) as batch_op:
        batch_op.alter_column(
            "pays_zip_ville_detail",
            existing_type=sa.VARCHAR(),
            nullable=True,
            existing_server_default=sa.text("''::character varying"),
        )
        batch_op.alter_column(
            "pays_zip_ville",
            existing_type=sa.VARCHAR(),
            nullable=True,
            existing_server_default=sa.text("''::character varying"),
        )

    with op.batch_alter_table("mkp_mission_offer", schema=None) as batch_op:
        batch_op.alter_column(
            "pays_zip_ville_detail",
            existing_type=sa.VARCHAR(),
            nullable=True,
            existing_server_default=sa.text("''::character varying"),
        )
        batch_op.alter_column(
            "pays_zip_ville",
            existing_type=sa.VARCHAR(),
            nullable=True,
            existing_server_default=sa.text("''::character varying"),
        )

    with op.batch_alter_table("mkp_job_offer", schema=None) as batch_op:
        batch_op.alter_column(
            "pays_zip_ville_detail",
            existing_type=sa.VARCHAR(),
            nullable=True,
            existing_server_default=sa.text("''::character varying"),
        )
        batch_op.alter_column(
            "pays_zip_ville",
            existing_type=sa.VARCHAR(),
            nullable=True,
            existing_server_default=sa.text("''::character varying"),
        )

    op.execute("ALTER TYPE profileenum RENAME TO adm_profileenum")
