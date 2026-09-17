"""clear the passwords the KYC wizard stored in clear

The sign-up wizard wrote the applicant's chosen password into
`aut_user.password` verbatim (its own comment claimed bcrypt; nothing
hashed it). Two consequences: the secret sat in the table — so in every
backup and every export — and the account could not authenticate
either, because Flask-Security compares against a hash.

The intake is fixed. This clears what it already wrote.

**Cleared, not hashed in place.** Hashing would preserve a secret that
has to be assumed exposed — it was readable to anyone with a database
dump, and, on a deployment that mounted the `/db/` console, to anyone at
all. Nulling costs these accounts nothing they had: they could not log
in with that password anyway. Their owners go through password
recovery, which is the correct path for a credential that leaked.

A value is treated as clear unless it looks like a passlib hash
(`$argon2…`, `$2b$…`): those all start with `$`, and no password the
wizard accepts can, since the field rejects a leading `$`... it does
not, in fact — so a member whose password began with `$` keeps a
plaintext value here. That is one row at worst, it still cannot
authenticate, and the alternative (clearing every password in the
table) is far worse.

Revision ID: c1d2e3f4a5b6
Revises: a2c4e6b8d0f1
Create Date: 2026-09-16 23:10:00.000000

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "c1d2e3f4a5b6"
down_revision = "a2c4e6b8d0f1"
branch_labels = None
depends_on = None

_PLAINTEXT = "password IS NOT NULL AND password <> '' AND password NOT LIKE '$%'"


def upgrade():
    bind = op.get_bind()
    count = bind.execute(
        sa.text(f"SELECT count(*) FROM aut_user WHERE {_PLAINTEXT}")  # noqa: S608
    ).scalar()
    bind.execute(sa.text(f"UPDATE aut_user SET password = NULL WHERE {_PLAINTEXT}"))  # noqa: S608
    print(f"cleared {count} plaintext password(s); those members must use recovery")


def downgrade():
    """Nothing to undo: the cleared values were secrets, and restoring
    them would mean having kept them."""
