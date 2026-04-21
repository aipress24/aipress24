"""biz offers: rename mission_application to offer_application, add projects + jobs tables

Revision ID: ab1c2d3e4f56
Revises: 949ffb955454
Create Date: 2026-04-21 18:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
import sqlalchemy_utils


# revision identifiers, used by Alembic.
revision = "ab1c2d3e4f56"
down_revision = "949ffb955454"
branch_labels = None
depends_on = None


_CONTRACT_TYPE = sa.Enum(
    "CDI", "CDD", "STAGE", "APPRENTISSAGE", "FREELANCE", name="contracttype"
)
_MISSION_STATUS_REUSE = postgresql.ENUM(
    "OPEN", "FILLED", "CLOSED", name="missionstatus", create_type=False
)


def upgrade():
    # ------------------------------------------------------------------
    # 1. Rename mkp_mission_application -> mkp_offer_application, migrate
    #    the mission_id column to offer_id and repoint the FK to
    #    mkp_content.id (all offer kinds share the same PK space).
    # ------------------------------------------------------------------
    op.rename_table("mkp_mission_application", "mkp_offer_application")

    with op.batch_alter_table("mkp_offer_application", schema=None) as batch_op:
        batch_op.alter_column(
            "mission_id",
            new_column_name="offer_id",
            existing_type=sa.BigInteger(),
            nullable=False,
        )
        batch_op.drop_constraint(
            "mkp_mission_application_mission_id_fkey", type_="foreignkey"
        )
        batch_op.create_foreign_key(
            "mkp_offer_application_offer_id_fkey",
            "mkp_content",
            ["offer_id"],
            ["id"],
            ondelete="CASCADE",
        )
        batch_op.drop_constraint(
            "uq_mkp_mission_application_user", type_="unique"
        )
        batch_op.create_unique_constraint(
            "uq_mkp_offer_application_user", ["offer_id", "owner_id"]
        )
        batch_op.add_column(
            sa.Column(
                "cv_url", sa.String(), nullable=False, server_default=""
            )
        )

    # ------------------------------------------------------------------
    # 2. New offer tables: mkp_project_offer and mkp_job_offer.
    # ------------------------------------------------------------------
    op.create_table(
        "mkp_project_offer",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("title", sa.String(), nullable=False, server_default=""),
        sa.Column("description", sa.String(), nullable=False, server_default=""),
        sa.Column("location", sa.String(), nullable=False, server_default=""),
        sa.Column("budget_min", sa.Integer(), nullable=True),
        sa.Column("budget_max", sa.Integer(), nullable=True),
        sa.Column("currency", sa.String(), nullable=False, server_default="EUR"),
        sa.Column("deadline", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "contact_email", sa.String(), nullable=False, server_default=""
        ),
        sa.Column("emitter_org_id", sa.BigInteger(), nullable=True),
        sa.Column(
            "mission_status",
            _MISSION_STATUS_REUSE,
            nullable=False,
            server_default="OPEN",
        ),
        sa.Column("team_size", sa.Integer(), nullable=True),
        sa.Column("duration_months", sa.Integer(), nullable=True),
        sa.Column(
            "project_type", sa.String(), nullable=False, server_default=""
        ),
        sa.Column("sector", sa.UnicodeText(), nullable=False, server_default=""),
        sa.Column(
            "section", sa.UnicodeText(), nullable=False, server_default=""
        ),
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
        "mkp_job_offer",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("title", sa.String(), nullable=False, server_default=""),
        sa.Column("description", sa.String(), nullable=False, server_default=""),
        sa.Column("location", sa.String(), nullable=False, server_default=""),
        sa.Column("salary_min", sa.Integer(), nullable=True),
        sa.Column("salary_max", sa.Integer(), nullable=True),
        sa.Column("currency", sa.String(), nullable=False, server_default="EUR"),
        sa.Column(
            "starting_date", sa.DateTime(timezone=True), nullable=True
        ),
        sa.Column(
            "contact_email", sa.String(), nullable=False, server_default=""
        ),
        sa.Column("emitter_org_id", sa.BigInteger(), nullable=True),
        sa.Column(
            "mission_status",
            _MISSION_STATUS_REUSE,
            nullable=False,
            server_default="OPEN",
        ),
        sa.Column(
            "contract_type",
            _CONTRACT_TYPE,
            nullable=False,
            server_default="CDI",
        ),
        sa.Column(
            "full_time", sa.Boolean(), nullable=False, server_default=sa.true()
        ),
        sa.Column(
            "remote_ok", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
        sa.Column("sector", sa.UnicodeText(), nullable=False, server_default=""),
        sa.Column(
            "section", sa.UnicodeText(), nullable=False, server_default=""
        ),
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


def downgrade():
    op.drop_table("mkp_job_offer")
    op.drop_table("mkp_project_offer")

    with op.batch_alter_table("mkp_offer_application", schema=None) as batch_op:
        batch_op.drop_column("cv_url")
        batch_op.drop_constraint(
            "uq_mkp_offer_application_user", type_="unique"
        )
        batch_op.create_unique_constraint(
            "uq_mkp_mission_application_user", ["offer_id", "owner_id"]
        )
        batch_op.drop_constraint(
            "mkp_offer_application_offer_id_fkey", type_="foreignkey"
        )
        batch_op.create_foreign_key(
            "mkp_mission_application_mission_id_fkey",
            "mkp_mission_offer",
            ["offer_id"],
            ["id"],
            ondelete="CASCADE",
        )
        batch_op.alter_column(
            "offer_id",
            new_column_name="mission_id",
            existing_type=sa.BigInteger(),
            nullable=False,
        )

    op.rename_table("mkp_offer_application", "mkp_mission_application")

    _CONTRACT_TYPE.drop(op.get_bind(), checkfirst=True)
