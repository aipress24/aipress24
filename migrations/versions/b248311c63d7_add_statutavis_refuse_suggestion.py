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

import sys

from alembic import op
from sqlalchemy.exc import ProgrammingError

# SQLSTATE for insufficient_privilege ("must be owner of type …").
_INSUFFICIENT_PRIVILEGE = "42501"

revision = "b248311c63d7"
down_revision = "80b4336ce752"
branch_labels = None
depends_on = None


_DDL = "ALTER TYPE statutavis ADD VALUE IF NOT EXISTS 'REFUSE_SUGGESTION'"


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        # `ALTER TYPE … ADD VALUE` is Postgres-only; the enum is a
        # plain VARCHAR on SQLite/other backends.
        return

    # Run the DDL on a SEPARATE AUTOCOMMIT connection, NOT via
    # `op.execute`, for two reasons:
    #
    # 1. The prod app DB role does not own the `statutavis` type
    #    (`InsufficientPrivilege: must be owner of type statutavis`)
    #    — same constraint that drove commit 98a243aa. We must let
    #    `flask db upgrade` finish so the rest of the release lands;
    #    a privilege failure on Alembic's own transaction would poison
    #    it and abort the whole upgrade (incl. the alembic_version
    #    bookkeeping). A side connection isolates the failure.
    # 2. AUTOCOMMIT also sidesteps the historical "ALTER TYPE … ADD
    #    VALUE cannot run inside a transaction block" caveat.
    #
    # If the role lacks ownership we degrade gracefully (project
    # philosophy, cf. 98a243aa): print the exact command an owner /
    # superuser must run, and continue. The unit guard
    # `TestStatutAvisPostgresEnumCoverage` still ensures the migration
    # exists; the missing value surfaces later as a clear write error
    # until an admin runs the one-liner.
    engine = bind.engine
    try:
        with engine.connect() as raw_conn:
            autocommit_conn = raw_conn.execution_options(isolation_level="AUTOCOMMIT")
            autocommit_conn.exec_driver_sql(_DDL)
    except ProgrammingError as exc:
        pgcode = getattr(getattr(exc, "orig", None), "pgcode", None)
        if pgcode != _INSUFFICIENT_PRIVILEGE:
            raise
        print(
            "\n"
            "================================================================\n"
            "  MIGRATION b248311c63d7 — privilege degraded (NOT fatal)\n"
            "  The deploy DB role does not own type `statutavis`, so\n"
            "  REFUSE_SUGGESTION was NOT added to the enum. The release\n"
            "  continues; writes of that status will 500 until an owner\n"
            "  / superuser runs ONE of:\n\n"
            f"    {_DDL};\n\n"
            "  -- or grant ownership once so future migrations work:\n"
            "    ALTER TYPE statutavis OWNER TO <app_db_role>;\n"
            "================================================================\n",
            file=sys.stderr,
        )


def downgrade() -> None:
    # Postgres cannot drop a value from an ENUM type without
    # recreating it; the precedent migration (d3369b39a653) likewise
    # leaves the added value in place on downgrade. No-op.
    pass
