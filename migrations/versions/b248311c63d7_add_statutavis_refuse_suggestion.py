"""add StatutAvis REFUSE_SUGGESTION enum value

Prod crash (2026-05-17):

    InvalidTextRepresentation: invalid input value for enum
    statutavis: "REFUSE_SUGGESTION"
    UPDATE nrm_contact_avis_enquete SET status='REFUSE_SUGGESTION' …

`StatutAvis` gained `REFUSE_SUGGESTION` in the Python model
(`sa.Enum(StatutAvis)` stores the member *name*, uppercase) but the
Postgres native ENUM type `statutavis` was never extended. SQLite
(test backend) treats the column as a permissive VARCHAR so the
suite stayed green — the exact lessons-learned #11 trap. The
precedent (`d3369b39a653`, ACCEPTE_RELATION_PRESSE) established that
each new StatutAvis member needs its own `ALTER TYPE … ADD VALUE`;
REFUSE_SUGGESTION's was missing.

`IF NOT EXISTS` keeps it idempotent on environments where the value
was already added out-of-band (drifted prod / re-run). Postgres-only
DDL; metadata-built test schemas already include the value via the
live Python enum, so this migration is a no-op there.

Revision ID: b248311c63d7
Revises: 80b4336ce752
Create Date: 2026-05-17
"""

from __future__ import annotations

from alembic import op

revision = "b248311c63d7"
down_revision = "80b4336ce752"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        # `ALTER TYPE … ADD VALUE` is Postgres-only; the enum is a
        # plain VARCHAR on SQLite/other backends.
        return
    op.execute("ALTER TYPE statutavis ADD VALUE IF NOT EXISTS 'REFUSE_SUGGESTION'")


def downgrade() -> None:
    # Postgres cannot drop a value from an ENUM type without
    # recreating it; the precedent migration (d3369b39a653) likewise
    # leaves the added value in place on downgrade. No-op.
    pass
