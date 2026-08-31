"""add pricing to events

Revision ID: b8c9d0e1f2a3
Revises: a7b8c9d0e1f2
Create Date: 2026-08-31

Trois colonnes sur les deux modèles d'événement (PRX-01) : la modalité
tarifaire, le prix en **centimes** et la devise. Aucun montant en
flottant, comme les budgets de `mkp_mission_offer`.

Aucune reprise à écrire : les événements existants deviennent
`FREE_FOR_ALL` avec un prix `NULL`, ce qui est le seul défaut qui
n'invente pas de tarif. C'est le `server_default` qui s'en charge.

`sa.Enum(StrEnum)` stocke le **nom** du membre : la colonne porte
« FREE_FOR_ALL » et non « free_for_all ». Écrire la forme minuscule
ferait lever `LookupError` à l'ORM en lecture.

Écrite à la main, comme les précédentes : `flask db migrate` ramasse
sur ce dépôt une dérive pré-existante, dont un `drop_column` sur
`evt_event_post.publisher_id`.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "b8c9d0e1f2a3"
down_revision = "a7b8c9d0e1f2"
branch_labels = None
depends_on = None

PRICINGS = ("FREE_FOR_ALL", "FREE_FOR_JOURNALISTS", "PAID")
TABLES = ("cnt_base", "evr_event")


def upgrade():
    # `add_column` n'émet pas le `CREATE TYPE` que `create_table` fait
    # tout seul : sans cette ligne, l'ajout échoue sur PostgreSQL avec
    # « type eventpricing does not exist ».
    postgresql.ENUM(*PRICINGS, name="eventpricing").create(
        op.get_bind(), checkfirst=True
    )

    for table in TABLES:
        with op.batch_alter_table(table, schema=None) as batch_op:
            batch_op.add_column(
                sa.Column(
                    "pricing",
                    sa.Enum(*PRICINGS, name="eventpricing"),
                    server_default="FREE_FOR_ALL",
                    nullable=False,
                )
            )
            # Nullable : `NULL` veut dire « pas de prix », ce qui est
            # l'état de tout événement gratuit pour tout le monde.
            batch_op.add_column(sa.Column("price", sa.Integer(), nullable=True))
            batch_op.add_column(
                sa.Column(
                    "currency", sa.String(), server_default="EUR", nullable=False
                )
            )


def downgrade():
    """Refuser de perdre un prix saisi.

    Aucune reprise n'a créé ces valeurs : un prix non nul est le fait
    d'un organisateur, et la descente le supprimerait sans trace.
    """
    bind = op.get_bind()
    counts = {
        "cnt_base": bind.execute(
            sa.text("SELECT count(*) FROM cnt_base WHERE price IS NOT NULL")
        ).scalar(),
        "evr_event": bind.execute(
            sa.text("SELECT count(*) FROM evr_event WHERE price IS NOT NULL")
        ).scalar(),
    }
    for table, count in counts.items():
        if count:
            msg = (
                f"Refus de supprimer les tarifs : {count} ligne(s) de {table} "
                "portent un prix saisi à la main. Les remettre à NULL avant "
                "de redescendre."
            )
            raise RuntimeError(msg)

    for table in reversed(TABLES):
        with op.batch_alter_table(table, schema=None) as batch_op:
            batch_op.drop_column("currency")
            batch_op.drop_column("price")
            batch_op.drop_column("pricing")

    postgresql.ENUM(name="eventpricing").drop(op.get_bind(), checkfirst=True)
