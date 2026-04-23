"""clean stale community roles

Revision ID: d3f7a49c20b1
Revises: a1c3f8b0e5d2
Create Date: 2026-04-23 07:45:00.000000

Regression cleanup: `append_user_role_from_community` used to stack
community roles onto a user instead of replacing the previous one, so
users who changed their KYC profile across communities ended up with
multiple community roles — and the union of their menus / ACLs.
Notably, Relations-Presse users who had once had a PRESS_MEDIA profile
kept seeing Newsroom.

This migration enforces the single-community invariant on the existing
DB: for every user with a `kyc_profile.profile_community`, keep only
the matching community role and drop the others. Non-community roles
(ADMIN, MANAGER, LEADER, ...) are untouched. The fix in the Python
helper (`set_user_role_from_community`) prevents the issue from
recurring.
"""
from __future__ import annotations

from alembic import op

# revision identifiers, used by Alembic.
revision = "d3f7a49c20b1"
down_revision = "a1c3f8b0e5d2"
branch_labels = None
depends_on = None


def upgrade():
    # Delete community-role memberships that don't match the user's
    # current profile_community. PostgreSQL-specific: uses
    # DELETE ... USING with a CASE-based expected-role derivation.
    op.execute(
        """
        DELETE FROM aut_roles_users aru
        USING aut_role r, kyc_profile kp
        WHERE aru.role_id = r.id
          AND aru.user_id = kp.user_id
          AND r.name IN (
              'PRESS_MEDIA', 'PRESS_RELATIONS', 'EXPERT',
              'TRANSFORMER', 'ACADEMIC'
          )
          AND r.name <> CASE kp.profile_community
              WHEN 'PRESS_MEDIA'     THEN 'PRESS_MEDIA'
              WHEN 'COMMUNICANTS'    THEN 'PRESS_RELATIONS'
              WHEN 'LEADERS_EXPERTS' THEN 'EXPERT'
              WHEN 'TRANSFORMERS'    THEN 'TRANSFORMER'
              WHEN 'ACADEMICS'       THEN 'ACADEMIC'
              ELSE NULL
          END
        """
    )


def downgrade():
    # Irreversible — we don't know which stale roles were dropped.
    pass
