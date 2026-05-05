"""biz: add pays_zip_ville to mission/project/job offers

Revision ID: c4d12a9b7e22
Revises: 576f28a34477
Create Date: 2026-05-05 12:00:00.000000

Ticket #0021 — embark the KYC geoloc on marketplace offers (missions,
projects, jobs). The free-text `location` column stays for back-compat ;
new edits target the structured pays/zip pair so the consult side can
filter by country and surface a labelled city.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "c4d12a9b7e22"
down_revision = "576f28a34477"
branch_labels = None
depends_on = None


_TABLES = ("mkp_mission_offer", "mkp_project_offer", "mkp_job_offer")


def upgrade():
    for table in _TABLES:
        op.add_column(
            table, sa.Column("pays_zip_ville", sa.String(), server_default="")
        )
        op.add_column(
            table, sa.Column("pays_zip_ville_detail", sa.String(), server_default="")
        )
    op.execute("UPDATE mkp_mission_offer SET pays_zip_ville = '', pays_zip_ville_detail = ''")
    op.execute("UPDATE mkp_project_offer SET pays_zip_ville = '', pays_zip_ville_detail = ''")
    op.execute("UPDATE mkp_job_offer SET pays_zip_ville = '', pays_zip_ville_detail = ''")


def downgrade():
    for table in _TABLES:
        op.drop_column(table, "pays_zip_ville_detail")
        op.drop_column(table, "pays_zip_ville")
