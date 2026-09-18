"""carry logo and banner onto the Business Walls that lost them

Re-subscribing creates a new `bw_business_wall` row, and the page reads
the *active* one. Organisations that renewed therefore lost their logo
and banner the day the new wall went live: the files were never
deleted, they simply stayed attached to the superseded row.

New walls now inherit them (`_carry_visual_identity`). This fills in the
ones created before that.

Only empty fields are filled, and only from the same organisation's own
earlier walls, most recently updated first. Both rows end up pointing at
the same stored object, which is safe here: nothing deletes a logo or a
banner blob.

Revision ID: d5e6f7a8b9c0
Revises: c1d2e3f4a5b6
Create Date: 2026-09-18 11:20:00.000000

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "d5e6f7a8b9c0"
down_revision = "c1d2e3f4a5b6"
branch_labels = None
depends_on = None

_FIELDS = (
    ("logo_image", "logo_image_copyright"),
    ("cover_image", "cover_image_copyright"),
)

# A lightweight table so the JSON columns serialise through SQLAlchemy;
# a raw `text()` update would hand psycopg a bare dict.
bw_table = sa.table(
    "bw_business_wall",
    sa.column("id"),
    sa.column("organisation_id"),
    sa.column("updated_at"),
    sa.column("logo_image", sa.JSON),
    sa.column("logo_image_copyright", sa.String),
    sa.column("cover_image", sa.JSON),
    sa.column("cover_image_copyright", sa.String),
)


def upgrade():
    bind = op.get_bind()
    rows = bind.execute(sa.select(bw_table).order_by(bw_table.c.updated_at.desc()))
    by_org: dict[object, list] = {}
    for row in rows.mappings():
        by_org.setdefault(row["organisation_id"], []).append(dict(row))

    filled = 0
    for walls in by_org.values():
        if len(walls) < 2:
            continue
        # Every wall of the organisation is filled, not just the active
        # one: which wall the page reads is the reader's business, and
        # a suspended wall reactivated later should not lose them again.
        for target in walls:
            updates = {}
            for image, copyright_ in _FIELDS:
                if target[image]:
                    continue
                donor = next((w for w in walls if w[image]), None)
                if donor is None:
                    continue
                updates[image] = donor[image]
                updates[copyright_] = donor[copyright_] or ""
            if not updates:
                continue
            bind.execute(
                bw_table.update().where(bw_table.c.id == target["id"]).values(**updates)
            )
            filled += 1
    print(f"carried logo/banner onto {filled} business wall(s)")


def downgrade():
    """Nothing to undo: the fields were empty, and the donor rows still
    hold their own copies."""
