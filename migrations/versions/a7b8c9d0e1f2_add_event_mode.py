"""add participation mode to events

Revision ID: a7b8c9d0e1f2
Revises: f6a7b8c9d0e1
Create Date: 2026-08-31

Trois colonnes sur les deux modèles d'événement (MOD-01, MOD-06) :
le mode de participation, la plateforme de visioconférence et les
modalités d'accès.

`sa.Enum(StrEnum)` stocke le **nom** du membre, pas sa valeur : la
colonne porte « ON_SITE » et non « on_site ». Écrire la forme
minuscule ferait lever `LookupError` à l'ORM en lecture — même piège
que la reprise `b1c2d3e4f5a6`.

Reprise MOD-05, en une requête par table : adresse et pas d'URL →
`ON_SITE` ; URL et pas d'adresse → `ONLINE` ; les deux → `HYBRID` ;
ni l'une ni l'autre → `ON_SITE`.

⚠️ **L'UPDATE de `cnt_base` est restreint à `type = 'event_post'`.**
Cette table porte tous les contenus — articles, communiqués, brèves,
commentaires — et `address` comme `url` y existent pour tous. Sans la
restriction, la requête passerait sans erreur et estamperait un mode
de participation sur chaque article du site.

Écrite à la main, comme les précédentes : `flask db migrate` ramasse
sur ce dépôt une dérive pré-existante, dont un `drop_column` sur
`evt_event_post.publisher_id`.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "a7b8c9d0e1f2"
down_revision = "f6a7b8c9d0e1"
branch_labels = None
depends_on = None

MODES = ("ON_SITE", "ONLINE", "HYBRID", "PHONE")
TABLES = ("cnt_base", "evr_event")

#: `cnt_base` est partagée par tous les contenus ; `evr_event` ne porte
#: que des événements et n'a pas de discriminant.
SCOPE = {"cnt_base": " AND type = 'event_post'", "evr_event": ""}


def upgrade():
    # `add_column` n'émet pas le `CREATE TYPE` que `create_table` fait
    # tout seul : sans cette ligne, l'ajout échoue sur PostgreSQL avec
    # « type eventmode does not exist ».
    postgresql.ENUM(*MODES, name="eventmode").create(op.get_bind(), checkfirst=True)

    for table in TABLES:
        with op.batch_alter_table(table, schema=None) as batch_op:
            batch_op.add_column(
                sa.Column(
                    "mode",
                    sa.Enum(*MODES, name="eventmode"),
                    server_default="ON_SITE",
                    nullable=False,
                )
            )
            batch_op.add_column(
                sa.Column("platform", sa.String(), server_default="", nullable=False)
            )
            batch_op.add_column(
                sa.Column(
                    "access_details", sa.String(), server_default="", nullable=False
                )
            )

    # PostgreSQL type le `CASE` en `text` et refuse de l'affecter à une
    # colonne d'énumération native ; SQLite, qui stocke la colonne en
    # `VARCHAR`, ne connaît pas la syntaxe de transtypage.
    cast = "::eventmode" if op.get_bind().dialect.name == "postgresql" else ""

    for table in TABLES:
        op.execute(
            sa.text(
                f"""
                UPDATE {table} SET mode = (CASE
                    WHEN coalesce(address, '') <> '' AND coalesce(url, '') <> ''
                        THEN 'HYBRID'
                    WHEN coalesce(url, '') <> '' AND coalesce(address, '') = ''
                        THEN 'ONLINE'
                    ELSE 'ON_SITE'
                END){cast}
                WHERE true{SCOPE[table]}
                """  # noqa: S608
            )
        )


def downgrade():
    for table in reversed(TABLES):
        with op.batch_alter_table(table, schema=None) as batch_op:
            batch_op.drop_column("access_details")
            batch_op.drop_column("platform")
            batch_op.drop_column("mode")

    postgresql.ENUM(name="eventmode").drop(op.get_bind(), checkfirst=True)
