# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""rename the Creative Commons licence to CC BY-NC-ND 4.0

Revision ID: 3b8f37dfacf2
Revises: d04237bc4c0c
Create Date: 2026-10-02 14:55:36.313538

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "3b8f37dfacf2"
down_revision = "d04237bc4c0c"
branch_labels = None
depends_on = None

OLD_CC = "Creative Commons (CC BY-ND)"
NEW_CC = "Creative Commons (CC BY-NC-ND 4.0)"


def upgrade() -> None:
    op.execute(
        sa.text(
            "UPDATE nrm_article SET copyright = :new WHERE copyright = :old"
        ).bindparams(new=NEW_CC, old=OLD_CC)
    )
    op.execute(
        sa.text(
            "UPDATE frt_content SET copyright = :new WHERE copyright = :old"
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
    op.execute(
        sa.text(
            "UPDATE frt_content SET copyright = :old WHERE copyright = :new"
        ).bindparams(new=NEW_CC, old=OLD_CC)
    )
    op.execute(
        "UPDATE frt_content SET copyright = ("
        " SELECT nrm_article.copyright FROM nrm_article"
        " WHERE nrm_article.id = frt_content.newsroom_id"
        ") WHERE type = 'article' AND newsroom_id IN (SELECT id FROM nrm_article)"
    )
