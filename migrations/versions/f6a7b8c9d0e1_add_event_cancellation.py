"""add cancellation to events

Revision ID: f6a7b8c9d0e1
Revises: e5a6b7c8d9f0
Create Date: 2026-08-31

Annuler n'est pas dépublier (ANN-03) : l'annonce a existé, elle reste
publique et barrée, et les accrédités doivent l'apprendre. D'où deux
colonnes plutôt qu'une valeur de plus dans `PublicationStatus`, qui est
partagée par tous les contenus.

`cancelled_at` est nullable — `NULL` veut dire « pas annulé », ce qui
est l'état de tous les événements déjà en base. `cancellation_reason`
porte `server_default=""` pour la même raison : rien à reprendre.

Écrite à la main, comme la migration `71b76649b829` et pour le même
motif — `flask db migrate` ramasse une dérive pré-existante entre les
modèles et la base, dont un `drop_column('publisher_id')` sur
`evt_event_post` dont dépendent les correctifs #0135/#0138.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "f6a7b8c9d0e1"
down_revision = "e5a6b7c8d9f0"
branch_labels = None
depends_on = None

TABLES = ("cnt_base", "evr_event")


def upgrade():
    for table in TABLES:
        with op.batch_alter_table(table, schema=None) as batch_op:
            batch_op.add_column(
                sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True)
            )
            batch_op.add_column(
                sa.Column(
                    "cancellation_reason",
                    sa.String(),
                    server_default="",
                    nullable=False,
                )
            )


def downgrade():
    """Refuser de perdre une annulation.

    Une annulation est un fait public déjà notifié à tous les
    accrédités (ANN-06). La descente rendrait l'événement de nouveau
    normal alors que ses inscrits ont reçu un message disant le
    contraire — un écart que rien ne rattraperait. Aucune reprise n'a
    créé ces lignes : toute valeur non nulle est le fait d'un
    organisateur.
    """
    bind = op.get_bind()
    counts = {
        "cnt_base": bind.execute(
            sa.text("SELECT count(*) FROM cnt_base WHERE cancelled_at IS NOT NULL")
        ).scalar(),
        "evr_event": bind.execute(
            sa.text("SELECT count(*) FROM evr_event WHERE cancelled_at IS NOT NULL")
        ).scalar(),
    }
    for table, count in counts.items():
        if count:
            msg = (
                f"Refus de retirer l'annulation : {count} ligne(s) de {table} "
                "portent une annulation déjà annoncée aux accrédités. "
                "Les rétablir ou les supprimer à la main avant de redescendre."
            )
            raise RuntimeError(msg)

    for table in reversed(TABLES):
        with op.batch_alter_table(table, schema=None) as batch_op:
            batch_op.drop_column("cancellation_reason")
            batch_op.drop_column("cancelled_at")
