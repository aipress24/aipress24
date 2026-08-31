"""add evt_accreditation and carry over the participations

Revision ID: a1c2e3d4b5f6
Revises: 71b76649b829
Create Date: 2026-08-30

First half of lot L1. Purely additive: the new table is created and
`evt_participation` is copied into it, but nothing reads the new table
yet and the old one is left in place. The application behaves
identically after this revision; the switch-over — and the rename of
`evt_participation` to `evt_participation_backup` — comes with the
second half, once `events/services.py` has been rewritten.

The existing participations were obtained without moderation, under a
model where clicking the button granted access outright. Turning them
into `ACCEPTED` is the only reading that dispossesses nobody.
`requested_at` and `decided_at` are set to the migration date: the
original dates were never recorded, and inventing them would be worse
than admitting they are unknown.

Hand-written. Autogenerate on this repository picks up unrelated
model/database drift — see the note in the events plan.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "a1c2e3d4b5f6"
down_revision = "71b76649b829"
branch_labels = None
depends_on = None

STATUS = sa.Enum(
    "REQUESTED", "ACCEPTED", "REJECTED", "WITHDRAWN", name="accreditationstatus"
)


def upgrade():
    # `create_table` emits the CREATE TYPE for the enum column itself;
    # creating it beforehand would duplicate it.
    op.create_table(
        "evt_accreditation",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("event_id", sa.BigInteger(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("status", STATUS, nullable=False),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("decided_by_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(
            ["event_id"], ["evt_event_post.id"], onupdate="CASCADE", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["aut_user.id"], onupdate="CASCADE", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["decided_by_id"], ["aut_user.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("event_id", "user_id", name="uq_evt_accreditation"),
    )
    op.create_index(
        "ix_evt_accreditation_event_status",
        "evt_accreditation",
        ["event_id", "status"],
    )
    op.create_index(
        "ix_evt_accreditation_user_status",
        "evt_accreditation",
        ["user_id", "status"],
    )

    # Reprise. `id` is generated here rather than by the application's
    # snowflake generator — these rows predate it, and nothing derives
    # meaning from their id.
    op.execute(
        sa.text(
            """
            INSERT INTO evt_accreditation
                (id, event_id, user_id, status, requested_at, decided_at)
            SELECT
                (row_number() OVER (ORDER BY p.event_id, p.user_id)) + 1000000000000,
                p.event_id, p.user_id, 'ACCEPTED', now(), now()
            FROM evt_participation p
            """
        )
    )


def downgrade():
    # Gardé comme son upgrade l'est. Après quelques jours
    # d'exploitation, cette table ne contient plus seulement la reprise
    # de `evt_participation` : elle porte les demandes reçues et les
    # décisions prises depuis. Un retour arrière les détruirait sans un
    # mot. On refuse, en disant quoi faire.
    bind = op.get_bind()
    carried = bind.execute(
        sa.text("SELECT count(*) FROM evt_accreditation WHERE status <> 'ACCEPTED'")
    ).scalar()
    if carried:
        msg = (
            f"Refus de supprimer evt_accreditation : {carried} ligne(s) ne "
            "proviennent pas de la reprise (demandes en cours, refus, "
            "désinscriptions). Les exporter avant de revenir en arrière, "
            "ou les supprimer sciemment."
        )
        raise RuntimeError(msg)

    op.drop_index("ix_evt_accreditation_user_status", table_name="evt_accreditation")
    op.drop_index("ix_evt_accreditation_event_status", table_name="evt_accreditation")
    op.drop_table("evt_accreditation")
    # `drop_table` leaves the enum type behind on PostgreSQL.
    STATUS.drop(op.get_bind(), checkfirst=True)
