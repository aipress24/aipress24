"""drop the five unused event subtypes

Revision ID: c0b1e2a3d4f5
Revises: ed562f9fc7fd
Create Date: 2026-08-30

`PublicEvent`, `PressEvent`, `TrainingEvent`, `CultureEvent` and
`ContestEvent` were siblings of `EventPost` under `EventPostBase`, each
with its own table. Nothing ever instantiated them: `event_receiver`
only creates `EventPost`, and the sole other caller — the events faker
generator — was an orphan module removed in lot C0a. Spec: ONG-03 and
ONG-03b of `specs/events-complements.md` §6.

Guarded on purpose. The tables are expected to be empty everywhere, but
"expected" is not "verified", and a stale row would leave `cnt_base`
carrying a polymorphic identity no mapper answers to — which breaks the
three queries that select `BaseContent` polymorphically
(`wip/crud/tables/contents.py`, `wip/views/publications.py`,
`wip/views/_tables.py`). Rather than discover that in production, the
migration refuses to run and says what to do.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "c0b1e2a3d4f5"
down_revision = "ed562f9fc7fd"
branch_labels = None
depends_on = None

TABLES = {
    "evt_public_event": "public_event",
    "evt_press_event": "press_event",
    "evt_training_event": "training_event",
    "evt_culture_event": "culture_event",
    "evt_contest_event": "contest_event",
}


def _refuse_if_populated() -> None:
    """Abort before dropping anything if a subtype row exists."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing = set(inspector.get_table_names())

    populated = []
    for table in TABLES:
        if table not in existing:
            continue
        stmt = sa.select(sa.func.count()).select_from(sa.table(table))
        count = bind.execute(stmt).scalar()
        if count:
            populated.append(f"{table} ({count})")

    if populated:
        msg = (
            "Refus de supprimer des sous-types d'événement non vides : "
            f"{', '.join(populated)}. Ces lignes sont invisibles dans "
            "l'application (toutes les vues interrogent EventPost) ; les "
            "reprendre en type='event_post' ou les supprimer, puis relancer."
        )
        raise RuntimeError(msg)


def upgrade():
    _refuse_if_populated()
    for table in TABLES:
        op.drop_table(table)


def downgrade():
    """Recreate the empty shells so the revision is reversible.

    The rows are not restored — the guard above guarantees there were
    none.
    """
    for table in TABLES:
        op.create_table(
            table,
            sa.Column("id", sa.BigInteger(), nullable=False),
            sa.ForeignKeyConstraint(["id"], ["cnt_base.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
