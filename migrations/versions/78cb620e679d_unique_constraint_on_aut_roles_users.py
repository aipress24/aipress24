"""unique constraint on aut_roles_users

Revision ID: 78cb620e679d
Revises: 8c401584035a
Create Date: 2026-05-26 16:51:59.956218

Defends against duplicate (user_id, role_id) rows in the user-role link
table. Such duplicates were observed in prod and used to crash
User.remove_role (fixed at the Python layer in 2f7d18cf — this is the
DB-level companion to that defence). Before adding the constraint we
collapse any existing duplicates, keeping a single row per (user, role)
pair via CTID.

"""
from __future__ import annotations

from alembic import op

revision = "78cb620e679d"
down_revision = "8c401584035a"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        DELETE FROM aut_roles_users a
        USING aut_roles_users b
        WHERE a.ctid < b.ctid
          AND a.user_id = b.user_id
          AND a.role_id = b.role_id
        """
    )
    op.create_unique_constraint(
        "uq_aut_roles_users_user_role",
        "aut_roles_users",
        ["user_id", "role_id"],
    )


def downgrade():
    op.drop_constraint(
        "uq_aut_roles_users_user_role",
        "aut_roles_users",
        type_="unique",
    )
