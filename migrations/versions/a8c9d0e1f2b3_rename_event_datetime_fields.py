"""Rename event datetime fields

Rename start_date/end_date to start_datetime/end_datetime for clarity,
and drop redundant start_time/end_time columns.

Revision ID: a8c9d0e1f2b3
Revises: 47bc345da251
Create Date: 2026-02-13 14:00:00.000000

"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "a8c9d0e1f2b3"
down_revision = "47bc345da251"
branch_labels = None
depends_on = None


def upgrade():
    # All columns are in cnt_base (inherited from EventPostBase -> BaseContent)
    with op.batch_alter_table("cnt_base", schema=None) as batch_op:
        # Rename columns for clarity (they store full datetimes, not just dates)
        batch_op.alter_column("start_date", new_column_name="start_datetime")
        batch_op.alter_column("end_date", new_column_name="end_datetime")
        # Drop redundant columns (start_time/end_time stored same data as start_date/end_date)
        batch_op.drop_column("start_time")
        batch_op.drop_column("end_time")


def downgrade():
    import sqlalchemy as sa
    from sqlalchemy_utils import ArrowType

    # All columns are in cnt_base
    with op.batch_alter_table("cnt_base", schema=None) as batch_op:
        # Rename columns back
        batch_op.alter_column("start_datetime", new_column_name="start_date")
        batch_op.alter_column("end_datetime", new_column_name="end_date")
        # Restore the redundant columns
        batch_op.add_column(
            sa.Column("start_time", ArrowType(timezone=True), nullable=True)
        )
        batch_op.add_column(
            sa.Column("end_time", ArrowType(timezone=True), nullable=True)
        )
