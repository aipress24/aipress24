"""fix_missing_field_competences

Revision ID: df70a0a218ae
Revises: 66eb37fc43e6
Create Date: 2025-09-19 16:30:00.000000

"""
from __future__ import annotations

import json

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "df70a0a218ae"
down_revision = "66eb37fc43e6"
branch_labels = None
depends_on = None


def upgrade():
    temp_table = sa.Table(
        "kyc_profile",
        sa.MetaData(),
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("info_personnelle", sa.JSON(), nullable=True),
        sa.Column("match_making", sa.JSON(), nullable=True),
    )
    connection = op.get_bind()
    for row in connection.execute(
        sa.select(
            temp_table.c.id,
            temp_table.c.info_personnelle,
            temp_table.c.match_making,
        )
    ):
        merged_info_personnelle = row.info_personnelle
        key = "competences_journalisme"
        merged_info_personnelle[key] = row.match_making.get(key, [])
        if key in row.match_making:
            del row.match_making[key]

        connection.execute(
            sa.text(
                "UPDATE kyc_profile SET info_personnelle = :info_perso, match_making = :match_making WHERE id = :id"
            ),
            {
                "info_perso": json.dumps(row.info_personnelle),
                "match_making": json.dumps(row.match_making),
                "id": row.id,
            },
        )


def downgrade():
    temp_table = sa.Table(
        "kyc_profile",
        sa.MetaData(),
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("info_personnelle", sa.JSON(), nullable=True),
        sa.Column("match_making", sa.JSON(), nullable=True),
    )
    connection = op.get_bind()
    for row in connection.execute(
        sa.select(
            temp_table.c.id,
            temp_table.c.info_personnelle,
            temp_table.c.match_making,
        )
    ):
        key = "competences_journalisme"
        competences_journalisme_value = row.info_personnelle.get(key, [])

        merged_match_making = row.match_making or {}
        merged_match_making[key] = competences_journalisme_value
        if key in row.info_personnelle:
            del row.info_personnelle[key]

        # Execute the update query
        connection.execute(
            sa.text(
                "UPDATE kyc_profile SET info_personnelle = :info_perso, match_making = :match_making WHERE id = :id"
            ),
            {
                "info_perso": json.dumps(row.info_personnelle),
                "match_making": json.dumps(merged_match_making),
                "id": row.id,
            },
        )
