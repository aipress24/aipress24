"""biz missions mvp

Revision ID: 949ffb955454
Revises: b2e45f891234
Create Date: 2026-04-21 17:22:27.002689

"""
from alembic import op
import sqlalchemy as sa
import sqlalchemy_utils


# revision identifiers, used by Alembic.
revision = "949ffb955454"
down_revision = "b2e45f891234"
branch_labels = None
depends_on = None


_MISSION_STATUS = sa.Enum("OPEN", "FILLED", "CLOSED", name="missionstatus")
_APPLICATION_STATUS = sa.Enum(
    "PENDING", "SELECTED", "REJECTED", name="applicationstatus"
)


def upgrade():
    op.create_table(
        "mkp_mission_offer",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("title", sa.String(), nullable=False, server_default=""),
        sa.Column(
            "description", sa.String(), nullable=False, server_default=""
        ),
        sa.Column("location", sa.String(), nullable=False, server_default=""),
        sa.Column("budget_min", sa.Integer(), nullable=True),
        sa.Column("budget_max", sa.Integer(), nullable=True),
        sa.Column(
            "currency", sa.String(), nullable=False, server_default="EUR"
        ),
        sa.Column("deadline", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "contact_email", sa.String(), nullable=False, server_default=""
        ),
        sa.Column("emitter_org_id", sa.BigInteger(), nullable=True),
        sa.Column(
            "mission_status",
            _MISSION_STATUS,
            nullable=False,
            server_default="OPEN",
        ),
        sa.Column("sector", sa.UnicodeText(), nullable=False, server_default=""),
        sa.Column("section", sa.UnicodeText(), nullable=False, server_default=""),
        sa.Column("genre", sa.UnicodeText(), nullable=False, server_default=""),
        sa.Column(
            "language",
            sa.Unicode(length=3),
            nullable=False,
            server_default="FRE",
        ),
        sa.Column("topic", sa.UnicodeText(), nullable=False, server_default=""),
        sa.Column(
            "published_at",
            sqlalchemy_utils.types.arrow.ArrowType(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "expired_at",
            sqlalchemy_utils.types.arrow.ArrowType(timezone=True),
            nullable=True,
        ),
        sa.Column("publisher_id", sa.BigInteger(), nullable=True),
        sa.ForeignKeyConstraint(["emitter_org_id"], ["crp_organisation.id"]),
        sa.ForeignKeyConstraint(["id"], ["mkp_content.id"]),
        sa.ForeignKeyConstraint(["publisher_id"], ["crp_organisation.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "mkp_mission_application",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("mission_id", sa.BigInteger(), nullable=False),
        sa.Column("message", sa.String(), nullable=False, server_default=""),
        sa.Column(
            "status",
            _APPLICATION_STATUS,
            nullable=False,
            server_default="PENDING",
        ),
        sa.Column(
            "created_at",
            sqlalchemy_utils.types.arrow.ArrowType(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "modified_at",
            sqlalchemy_utils.types.arrow.ArrowType(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "deleted_at",
            sqlalchemy_utils.types.arrow.ArrowType(timezone=True),
            nullable=True,
        ),
        sa.Column("owner_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["mission_id"], ["mkp_mission_offer.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["owner_id"], ["aut_user.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "mission_id",
            "owner_id",
            name="uq_mkp_mission_application_user",
        ),
    )


def downgrade():
    op.drop_table("mkp_mission_application")
    op.drop_table("mkp_mission_offer")
    _APPLICATION_STATUS.drop(op.get_bind(), checkfirst=True)
    _MISSION_STATUS.drop(op.get_bind(), checkfirst=True)
