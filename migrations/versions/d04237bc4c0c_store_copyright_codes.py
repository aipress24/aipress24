# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""store the copyright mention as a code, not as its label

Revision ID: d04237bc4c0c
Revises: 5d004245b5f2
Create Date: 2026-09-28 18:00:00.000000

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "d04237bc4c0c"
down_revision = "5d004245b5f2"
branch_labels = None
depends_on = None

LABELS_TO_CODES = {
    "Tous droits réservés": "all-rights-reserved",
    "Creative Commons (CC BY-ND)": "cc-by-nd",
}
TABLES = ("nrm_article", "frt_content")


def upgrade() -> None:
    _rewrite(LABELS_TO_CODES)


def downgrade() -> None:
    _rewrite({code: label for label, code in LABELS_TO_CODES.items()})


def _rewrite(mapping: dict[str, str]) -> None:
    for name in TABLES:
        table = sa.table(name, sa.column("copyright"))
        for old, new in mapping.items():
            op.execute(
                table.update().where(table.c.copyright == old).values(copyright=new)
            )
