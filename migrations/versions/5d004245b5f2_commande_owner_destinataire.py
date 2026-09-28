# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""commande: owner is whoever places it, add destinataire_id and CANCELLED

A commande born from an accepted sujet held the journalist in `owner_id`
and the rédac chef in `commanditaire_id`. The owner is now whoever places
the commande; the journalist moves to the new `destinataire_id`, and the
media the commande is placed for becomes its `publisher_id`.

Revision ID: 5d004245b5f2
Revises: 74a6a9b5afe2
Create Date: 2026-09-28 15:00:00.000000

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "5d004245b5f2"
down_revision = "74a6a9b5afe2"
branch_labels = None
depends_on = None

FK_NAME = "fk_nrm_commande_destinataire_id"
INDEX_NAME = "ix_nrm_commande_destinataire_id"


def upgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.execute("ALTER TYPE publicationstatus ADD VALUE IF NOT EXISTS 'CANCELLED'")

    with op.batch_alter_table("nrm_commande", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("destinataire_id", sa.BigInteger(), nullable=True)
        )
        batch_op.create_foreign_key(FK_NAME, "aut_user", ["destinataire_id"], ["id"])
        batch_op.create_index(INDEX_NAME, ["destinataire_id"])

    # Born from a sujet: the two roles differ. The SET clauses all read the
    # row as it was before the update.
    op.execute(
        "UPDATE nrm_commande SET destinataire_id = owner_id,"
        " owner_id = commanditaire_id, publisher_id = media_id"
        " WHERE owner_id <> commanditaire_id"
    )


def downgrade() -> None:
    # The previous publisher_id of a commande born from a sujet is lost; the
    # CANCELLED enum value stays, PostgreSQL cannot drop one.
    op.execute(
        "UPDATE nrm_commande SET owner_id = destinataire_id"
        " WHERE destinataire_id IS NOT NULL AND owner_id = commanditaire_id"
    )
    with op.batch_alter_table("nrm_commande", schema=None) as batch_op:
        batch_op.drop_index(INDEX_NAME)
        batch_op.drop_constraint(FK_NAME, type_="foreignkey")
        batch_op.drop_column("destinataire_id")
