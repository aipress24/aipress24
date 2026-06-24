"""backfill legacy mission categories to JOURNALISME (#0224)

Revision ID: b1c2d3e4f5a6
Revises: a0b1c2d3e4f5
Create Date: 2026-06-24 20:15:00.000000

Bug #0224 — the Press & Media visibility gate keys on
`category == JOURNALISME`, so missions whose `category` is NULL leaked to
every community. Such rows are all journalism: the `category` column was
introduced by #0185 (migration 3c4d5e6f7a8b) and the marketplace was
journalism-only before that — Project / Job offers are separate models,
and the communication / innovation categories were *introduced by* #0185.
So every NULL-category mission is a legacy journalism mission.

NB: the column stores the enum NAME (`Enum(MissionCategory)`), i.e. the
uppercase 'JOURNALISME', not the lowercase value 'journalisme'. Writing
the lowercase form would make the ORM raise LookupError on read.

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = 'b1c2d3e4f5a6'
down_revision = 'a0b1c2d3e4f5'
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        "UPDATE mkp_mission_offer SET category = 'JOURNALISME' "
        "WHERE category IS NULL"
    )


def downgrade():
    # Irreversible : once backfilled we can't tell a row that was always
    # 'JOURNALISME' from one we set here, so nulling them back would also
    # wipe genuinely-journalism categories. Leave the data in place.
    pass
