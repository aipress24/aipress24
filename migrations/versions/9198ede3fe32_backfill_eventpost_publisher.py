"""Back-fill EventPost.publisher_id from Event.publisher_id

Bugs #0135 and #0138: until commit 8a50dbd5 the events receiver did
not propagate publisher_id from the source Event onto the publicly-
listed EventPost. Real events created before the fix sit in production
with EventPost.publisher_id = NULL, which keeps them invisible on the
client's Business Wall (the BW query filters on publisher_id ==
org.id).

This migration walks every EventPost whose publisher_id is NULL and
copies the value from the matching Event (linked via
evt_event_post.eventroom_id = evr_event.id). Idempotent — re-running
is a no-op since the second pass finds nothing to back-fill.

Revision ID: 9198ede3fe32
Revises: fe9ab2b94cf4
Create Date: 2026-05-13
"""

from __future__ import annotations

from alembic import op

revision = "9198ede3fe32"
down_revision = "fe9ab2b94cf4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE evt_event_post AS p
        SET publisher_id = e.publisher_id
        FROM evr_event AS e
        WHERE p.eventroom_id = e.id
          AND p.publisher_id IS NULL
          AND e.publisher_id IS NOT NULL
        """
    )


def downgrade() -> None:
    # No-op: we can't tell which posts had publisher_id NULL before
    # the back-fill. Leaving the values in place is safe.
    pass
