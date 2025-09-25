"""2-level ontology for metier

Revision ID: 52281ec23a71
Revises: 7050901cbd74
Create Date: 2025-09-25 14:40:24.852876

"""

from __future__ import annotations

# import sqlalchemy as sa
from alembic import op
from sqlalchemy.sql import text

# revision identifiers, used by Alembic.
revision = "52281ec23a71"
down_revision = "7050901cbd74"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        text(
            """
                UPDATE kyc_profile
                SET info_personnelle = JSONB_SET(
                    JSONB_SET(
                        info_personnelle,
                        '{metier_principal}',
                        '[]',
                        true
                    ),
                    '{metier_principal_detail}',
                    '[]',
                    true
                );
                """
        )
    )


def downgrade():
    op.execute(
        text(
            """
                UPDATE kyc_profile
                SET
                    info_personnelle = info_personnelle - 'metier_principal_detail',
                    info_personnelle = JSONB_SET(
                        info_personnelle,
                        '{metier_principal}',
                        '""',
                        true
                    );
                """
        )
    )
