"""add organiser to events

Revision ID: d0e1f2a3b4c5
Revises: c9d0e1f2a3b4
Create Date: 2026-08-31

Deux colonnes sur les deux modèles d'événement : l'organisateur,
distinct de l'éditeur (ORG-01). Une agence RP publie pour son client —
l'éditeur est l'agence, l'organisateur est le client.

Aucune reprise : les deux champs sont facultatifs (ORG-02), et à vide
l'organisateur affiché reste l'éditeur, ce qui reproduit exactement le
comportement actuel.

`organiser_id` est une **seconde** clé étrangère vers
`crp_organisation` sur les mêmes tables que `publisher_id`. Les deux
relations ORM portent donc un `foreign_keys=` explicite, sans quoi
SQLAlchemy ne saurait pas laquelle joindre.

Écrite à la main, comme les précédentes.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "d0e1f2a3b4c5"
down_revision = "c9d0e1f2a3b4"
branch_labels = None
depends_on = None

TABLES = ("cnt_base", "evr_event")


def upgrade():
    for table in TABLES:
        with op.batch_alter_table(table, schema=None) as batch_op:
            batch_op.add_column(
                sa.Column("organiser_id", sa.BigInteger(), nullable=True)
            )
            batch_op.add_column(
                sa.Column(
                    "organiser_name",
                    sa.String(),
                    server_default="",
                    nullable=False,
                )
            )
            batch_op.create_foreign_key(
                f"fk_{table}_organiser_id_crp_organisation",
                "crp_organisation",
                ["organiser_id"],
                ["id"],
            )


def downgrade():
    """Descente franche.

    Contrairement à l'annulation et au tarif, il n'y a pas de fait
    public à perdre : à vide, l'organisateur affiché redevient
    l'éditeur, ce qui est l'état d'avant le lot.
    """
    for table in reversed(TABLES):
        with op.batch_alter_table(table, schema=None) as batch_op:
            batch_op.drop_constraint(
                f"fk_{table}_organiser_id_crp_organisation", type_="foreignkey"
            )
            batch_op.drop_column("organiser_name")
            batch_op.drop_column("organiser_id")
