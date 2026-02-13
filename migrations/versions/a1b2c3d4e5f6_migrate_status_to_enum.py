# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Migrate Sujet, Commande, AvisEnquete status from VARCHAR to PublicationStatus enum.

Revision ID: a1b2c3d4e5f6
Revises: 9763afdb9033
Create Date: 2026-01-08 17:00:00.000000

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "a1b2c3d4e5f6"
down_revision = "9763afdb9033"
branch_labels = None
depends_on = None


def upgrade():
    # The publicationstatus enum already exists (used by nrm_article, crm_communique, evr_event)
    # We just need to:
    # 1. Convert empty string values to 'DRAFT'
    # 2. Convert the column type from VARCHAR to the enum

    # nrm_sujet
    op.execute(
        "UPDATE nrm_sujet SET status = 'DRAFT' WHERE status = '' OR status IS NULL"
    )
    with op.batch_alter_table("nrm_sujet", schema=None) as batch_op:
        batch_op.alter_column(
            "status",
            existing_type=sa.VARCHAR(),
            type_=sa.Enum(
                "DRAFT",
                "PRIVATE",
                "PENDING",
                "PUBLIC",
                "REJECTED",
                "EXPIRED",
                "ARCHIVED",
                "DELETED",
                name="publicationstatus",
            ),
            existing_nullable=False,
            postgresql_using="status::publicationstatus",
        )

    # nrm_commande
    op.execute(
        "UPDATE nrm_commande SET status = 'DRAFT' WHERE status = '' OR status IS NULL"
    )
    with op.batch_alter_table("nrm_commande", schema=None) as batch_op:
        batch_op.alter_column(
            "status",
            existing_type=sa.VARCHAR(),
            type_=sa.Enum(
                "DRAFT",
                "PRIVATE",
                "PENDING",
                "PUBLIC",
                "REJECTED",
                "EXPIRED",
                "ARCHIVED",
                "DELETED",
                name="publicationstatus",
            ),
            existing_nullable=False,
            postgresql_using="status::publicationstatus",
        )

    # nrm_avis_enquete
    op.execute(
        "UPDATE nrm_avis_enquete SET status = 'DRAFT' WHERE status = '' OR status IS NULL"
    )
    with op.batch_alter_table("nrm_avis_enquete", schema=None) as batch_op:
        batch_op.alter_column(
            "status",
            existing_type=sa.VARCHAR(),
            type_=sa.Enum(
                "DRAFT",
                "PRIVATE",
                "PENDING",
                "PUBLIC",
                "REJECTED",
                "EXPIRED",
                "ARCHIVED",
                "DELETED",
                name="publicationstatus",
            ),
            existing_nullable=False,
            postgresql_using="status::publicationstatus",
        )


def downgrade():
    # Convert back to VARCHAR

    with op.batch_alter_table("nrm_avis_enquete", schema=None) as batch_op:
        batch_op.alter_column(
            "status",
            existing_type=sa.Enum(
                "DRAFT",
                "PRIVATE",
                "PENDING",
                "PUBLIC",
                "REJECTED",
                "EXPIRED",
                "ARCHIVED",
                "DELETED",
                name="publicationstatus",
            ),
            type_=sa.VARCHAR(),
            existing_nullable=False,
            postgresql_using="status::text",
        )

    with op.batch_alter_table("nrm_commande", schema=None) as batch_op:
        batch_op.alter_column(
            "status",
            existing_type=sa.Enum(
                "DRAFT",
                "PRIVATE",
                "PENDING",
                "PUBLIC",
                "REJECTED",
                "EXPIRED",
                "ARCHIVED",
                "DELETED",
                name="publicationstatus",
            ),
            type_=sa.VARCHAR(),
            existing_nullable=False,
            postgresql_using="status::text",
        )

    with op.batch_alter_table("nrm_sujet", schema=None) as batch_op:
        batch_op.alter_column(
            "status",
            existing_type=sa.Enum(
                "DRAFT",
                "PRIVATE",
                "PENDING",
                "PUBLIC",
                "REJECTED",
                "EXPIRED",
                "ARCHIVED",
                "DELETED",
                name="publicationstatus",
            ),
            type_=sa.VARCHAR(),
            existing_nullable=False,
            postgresql_using="status::text",
        )
