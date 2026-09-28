# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""add copyright to post, rename the Creative Commons licence to CC BY-ND

Revision ID: 74a6a9b5afe2
Revises: b3c4d5e6f7a8
Create Date: 2026-09-28 12:00:00.000000

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "74a6a9b5afe2"
down_revision = "b3c4d5e6f7a8"
branch_labels = None
depends_on = None

OLD_CC = "Creative Commons (CC-BY-SA-ND)"
NEW_CC = "Creative Commons (CC BY-ND)"


def upgrade() -> None:
    with op.batch_alter_table("frt_content", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("copyright", sa.String(), server_default="", nullable=False)
        )

    op.execute(
        sa.text(
            "UPDATE nrm_article SET copyright = :new WHERE copyright = :old"
        ).bindparams(new=NEW_CC, old=OLD_CC)
    )
    op.execute(
        "UPDATE frt_content SET copyright = ("
        " SELECT nrm_article.copyright FROM nrm_article"
        " WHERE nrm_article.id = frt_content.newsroom_id"
        ") WHERE type = 'article' AND newsroom_id IN (SELECT id FROM nrm_article)"
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            "UPDATE nrm_article SET copyright = :old WHERE copyright = :new"
        ).bindparams(new=NEW_CC, old=OLD_CC)
    )
    with op.batch_alter_table("frt_content", schema=None) as batch_op:
        batch_op.drop_column("copyright")
