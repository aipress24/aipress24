"""Ticket #0198 : project_category on ProjectOffer

Revision ID: 8b9c0d1e2f3a
Revises: 7a8b9c0d1e2f
Create Date: 2026-06-09 13:00:00.000000

Erick #0198 : « rajouter dans MARKET/Projects les types de projets
(Journalisme, Communication, Innovation) » with a sub-type drawn
from the per-category ontology. We store the top-level value in a
new `project_category` column ; the existing free-text `project_type`
column is repurposed to hold the sub-type (admin-editable in
/admin/ontology/?taxonomy_name=type_projet_*).
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "8b9c0d1e2f3a"
down_revision = "7a8b9c0d1e2f"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("mkp_project_offer", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "project_category",
                sa.String(),
                nullable=False,
                server_default="",
            )
        )


def downgrade():
    with op.batch_alter_table("mkp_project_offer", schema=None) as batch_op:
        batch_op.drop_column("project_category")
