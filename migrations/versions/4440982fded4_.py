"""empty message

Revision ID: 4440982fded4
Revises: a674e53fdff0
Create Date: 2025-04-04 11:00:25.172574

"""

from alembic import op
import sqlalchemy as sa
import sqlalchemy_utils

from sqlalchemy.dialects import postgresql
from sqlalchemy_utils import ArrowType

# revision identifiers, used by Alembic.
revision = "4440982fded4"
down_revision = "a674e53fdff0"
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    poststatus = sa.Enum("DRAFT", "PUBLIC", "ARCHIVED", name="poststatus3")

    op.create_table(
        "frt_content",
        sa.Column("type", sa.String(), nullable=False),
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("owner_id", sa.Integer(), nullable=False),
        sa.Column("view_count", sa.Integer(), nullable=False),
        sa.Column("like_count", sa.Integer(), nullable=False),
        sa.Column("comment_count", sa.Integer(), nullable=False),
        sa.Column("content", sa.String(), nullable=False),
        sa.Column("created_at", ArrowType(timezone=True), nullable=False),
        sa.Column("modified_at", ArrowType(timezone=True), nullable=True),
        sa.Column("deleted_at", ArrowType(timezone=True), nullable=True),
        sa.Column("object_id", sa.String(), nullable=True),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("summary", sa.String(), nullable=False),
        sa.Column("status", poststatus, nullable=False),
        sa.Column("published_at", ArrowType(timezone=True), nullable=True),
        sa.Column("last_updated_at", ArrowType(timezone=True), nullable=True),
        sa.Column("expires_at", ArrowType(timezone=True), nullable=True),
        sa.Column("publisher_id", sa.BigInteger(), nullable=True),
        sa.Column("image_id", sa.BigInteger(), nullable=True),
        sa.Column("newsroom_id", sa.BigInteger(), nullable=True),
        sa.Column(
            "publisher_type",
            sa.Enum("AGENCY", "MEDIA", name="publishertype2"),
            nullable=False,
        ),
        sa.Column("genre", sa.String(), nullable=False),
        sa.Column("section", sa.String(), nullable=False),
        sa.Column("topic", sa.String(), nullable=False),
        sa.Column("sector", sa.String(), nullable=False),
        sa.Column("geo_localisation", sa.String(), nullable=False),
        sa.Column("language", sa.String(), nullable=False),
        sa.ForeignKeyConstraint(
            ["owner_id"],
            ["aut_user.id"],
        ),
        sa.ForeignKeyConstraint(
            ["publisher_id"],
            ["crp_organisation.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("frt_content", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_frt_content_newsroom_id"), ["newsroom_id"], unique=False
        )
        batch_op.create_index(
            batch_op.f("ix_frt_content_object_id"), ["object_id"], unique=False
        )

    # Drop old tables
    op.drop_table("wir_press_release")
    op.drop_table("wir_article")
    op.drop_table("edt_image")
    op.drop_table("edt_visual")
    op.drop_table("edt_multimedia")
    op.drop_table("edt_article")
    op.drop_table("com_press_release")
    op.drop_table("edt_text")
    op.drop_table("edt_editorial")
    op.drop_table("soc_post")
    with op.batch_alter_table("soc_comment", schema=None) as batch_op:
        batch_op.drop_index("ix_soc_comment_object_id")

    op.drop_table("soc_comment")

    # Add FKs
    with op.batch_alter_table("soc_likes", schema=None) as batch_op:
        batch_op.drop_constraint("soc_likes_content_id_fkey", type_="foreignkey")
        batch_op.create_foreign_key(
            None,
            "frt_content",
            ["content_id"],
            ["id"],
            onupdate="CASCADE",
            ondelete="CASCADE",
        )

    with op.batch_alter_table("tag_application", schema=None) as batch_op:
        batch_op.drop_constraint("tag_application_object_id_fkey", type_="foreignkey")
        batch_op.create_foreign_key(
            None, "frt_content", ["object_id"], ["id"], ondelete="CASCADE"
        )

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table("tag_application", schema=None) as batch_op:
        batch_op.drop_constraint(None, type_="foreignkey")
        batch_op.create_foreign_key(
            "tag_application_object_id_fkey",
            "cnt_base",
            ["object_id"],
            ["id"],
            ondelete="CASCADE",
        )

    with op.batch_alter_table("soc_likes", schema=None) as batch_op:
        batch_op.drop_constraint(None, type_="foreignkey")
        batch_op.create_foreign_key(
            "soc_likes_content_id_fkey",
            "cnt_base",
            ["content_id"],
            ["id"],
            onupdate="CASCADE",
            ondelete="CASCADE",
        )

    op.create_table(
        "edt_image",
        sa.Column("id", sa.BIGINT(), autoincrement=False, nullable=False),
        sa.Column("subtype", sa.VARCHAR(), autoincrement=False, nullable=False),
        sa.ForeignKeyConstraint(["id"], ["edt_visual.id"], name="edt_image_id_fkey"),
        sa.PrimaryKeyConstraint("id", name="edt_image_pkey"),
    )
    op.create_table(
        "soc_comment",
        sa.Column("content", sa.VARCHAR(), autoincrement=False, nullable=False),
        sa.Column("object_id", sa.VARCHAR(), autoincrement=False, nullable=False),
        sa.Column("id", sa.BIGINT(), autoincrement=True, nullable=False),
        sa.Column("owner_id", sa.INTEGER(), autoincrement=False, nullable=False),
        sa.Column(
            "created_at",
            postgresql.TIMESTAMP(timezone=True),
            autoincrement=False,
            nullable=False,
        ),
        sa.Column(
            "modified_at",
            postgresql.TIMESTAMP(timezone=True),
            autoincrement=False,
            nullable=True,
        ),
        sa.Column(
            "deleted_at",
            postgresql.TIMESTAMP(timezone=True),
            autoincrement=False,
            nullable=True,
        ),
        sa.ForeignKeyConstraint(
            ["owner_id"], ["aut_user.id"], name="soc_comment_owner_id_fkey"
        ),
        sa.PrimaryKeyConstraint("id", name="soc_comment_pkey"),
    )
    with op.batch_alter_table("soc_comment", schema=None) as batch_op:
        batch_op.create_index("ix_soc_comment_object_id", ["object_id"], unique=False)

    op.create_table(
        "wir_article",
        sa.Column("newsroom_id", sa.BIGINT(), autoincrement=False, nullable=False),
        sa.Column(
            "publisher_type",
            postgresql.ENUM("AGENCY", "MEDIA", name="publishertype"),
            autoincrement=False,
            nullable=False,
        ),
        sa.Column("title", sa.VARCHAR(), autoincrement=False, nullable=False),
        sa.Column("content", sa.VARCHAR(), autoincrement=False, nullable=False),
        sa.Column("summary", sa.VARCHAR(), autoincrement=False, nullable=False),
        sa.Column(
            "status",
            postgresql.ENUM("DRAFT", "PUBLIC", "ARCHIVED", name="poststatus"),
            autoincrement=False,
            nullable=False,
        ),
        sa.Column(
            "published_at",
            postgresql.TIMESTAMP(timezone=True),
            autoincrement=False,
            nullable=True,
        ),
        sa.Column(
            "last_updated_at",
            postgresql.TIMESTAMP(timezone=True),
            autoincrement=False,
            nullable=True,
        ),
        sa.Column(
            "expires_at",
            postgresql.TIMESTAMP(timezone=True),
            autoincrement=False,
            nullable=True,
        ),
        sa.Column("publisher_id", sa.BIGINT(), autoincrement=False, nullable=True),
        sa.Column("image_id", sa.BIGINT(), autoincrement=False, nullable=True),
        sa.Column("id", sa.BIGINT(), autoincrement=False, nullable=False),
        sa.Column(
            "created_at",
            postgresql.TIMESTAMP(timezone=True),
            autoincrement=False,
            nullable=False,
        ),
        sa.Column(
            "modified_at",
            postgresql.TIMESTAMP(timezone=True),
            autoincrement=False,
            nullable=True,
        ),
        sa.Column(
            "deleted_at",
            postgresql.TIMESTAMP(timezone=True),
            autoincrement=False,
            nullable=True,
        ),
        sa.Column("owner_id", sa.INTEGER(), autoincrement=False, nullable=False),
        sa.Column("genre", sa.VARCHAR(), autoincrement=False, nullable=False),
        sa.Column("section", sa.VARCHAR(), autoincrement=False, nullable=False),
        sa.Column("topic", sa.VARCHAR(), autoincrement=False, nullable=False),
        sa.Column("sector", sa.VARCHAR(), autoincrement=False, nullable=False),
        sa.Column(
            "geo_localisation", sa.VARCHAR(), autoincrement=False, nullable=False
        ),
        sa.Column("language", sa.VARCHAR(), autoincrement=False, nullable=False),
        sa.Column("view_count", sa.INTEGER(), autoincrement=False, nullable=False),
        sa.Column("like_count", sa.INTEGER(), autoincrement=False, nullable=False),
        sa.Column("comment_count", sa.INTEGER(), autoincrement=False, nullable=False),
        sa.ForeignKeyConstraint(
            ["owner_id"], ["aut_user.id"], name="wir_article_owner_id_fkey"
        ),
        sa.ForeignKeyConstraint(
            ["publisher_id"],
            ["crp_organisation.id"],
            name="wir_article_publisher_id_fkey",
        ),
        sa.PrimaryKeyConstraint("newsroom_id", "id", name="wir_article_pkey"),
    )
    op.create_table(
        "soc_post",
        sa.Column("content", sa.VARCHAR(), autoincrement=False, nullable=False),
        sa.Column("id", sa.BIGINT(), autoincrement=True, nullable=False),
        sa.Column("owner_id", sa.INTEGER(), autoincrement=False, nullable=False),
        sa.Column(
            "created_at",
            postgresql.TIMESTAMP(timezone=True),
            autoincrement=False,
            nullable=False,
        ),
        sa.Column(
            "modified_at",
            postgresql.TIMESTAMP(timezone=True),
            autoincrement=False,
            nullable=True,
        ),
        sa.Column(
            "deleted_at",
            postgresql.TIMESTAMP(timezone=True),
            autoincrement=False,
            nullable=True,
        ),
        sa.Column("view_count", sa.INTEGER(), autoincrement=False, nullable=False),
        sa.Column("like_count", sa.INTEGER(), autoincrement=False, nullable=False),
        sa.Column("comment_count", sa.INTEGER(), autoincrement=False, nullable=False),
        sa.ForeignKeyConstraint(
            ["owner_id"], ["aut_user.id"], name="soc_post_owner_id_fkey"
        ),
        sa.PrimaryKeyConstraint("id", name="soc_post_pkey"),
    )
    op.create_table(
        "edt_editorial",
        sa.Column("id", sa.BIGINT(), autoincrement=False, nullable=False),
        sa.Column("info_source", sa.VARCHAR(), autoincrement=False, nullable=False),
        sa.Column("view_count", sa.INTEGER(), autoincrement=False, nullable=False),
        sa.Column("like_count", sa.INTEGER(), autoincrement=False, nullable=False),
        sa.Column("comment_count", sa.INTEGER(), autoincrement=False, nullable=False),
        sa.Column(
            "status",
            postgresql.ENUM(
                "DRAFT",
                "PRIVATE",
                "PENDING",
                "PUBLIC",
                "REJECTED",
                "EXPIRED",
                "ARCHIVED",
                "DELETED",
                name="publicationstatus",
            ),
            autoincrement=False,
            nullable=True,
        ),
        sa.Column(
            "published_at",
            postgresql.TIMESTAMP(timezone=True),
            autoincrement=False,
            nullable=True,
        ),
        sa.Column(
            "expired_at",
            postgresql.TIMESTAMP(timezone=True),
            autoincrement=False,
            nullable=True,
        ),
        sa.Column("publisher_id", sa.BIGINT(), autoincrement=False, nullable=True),
        sa.Column("sector", sa.TEXT(), autoincrement=False, nullable=False),
        sa.Column("section", sa.TEXT(), autoincrement=False, nullable=False),
        sa.Column("genre", sa.TEXT(), autoincrement=False, nullable=False),
        sa.Column(
            "language", sa.VARCHAR(length=3), autoincrement=False, nullable=False
        ),
        sa.Column("topic", sa.TEXT(), autoincrement=False, nullable=False),
        sa.Column("copyright_holder", sa.TEXT(), autoincrement=False, nullable=True),
        sa.Column("copyright_notice", sa.TEXT(), autoincrement=False, nullable=True),
        sa.Column("_fts", sa.TEXT(), autoincrement=False, nullable=False),
        sa.Column("address", sa.VARCHAR(), autoincrement=False, nullable=False),
        sa.Column("city", sa.VARCHAR(), autoincrement=False, nullable=False),
        sa.Column("region", sa.VARCHAR(), autoincrement=False, nullable=False),
        sa.Column("departement", sa.VARCHAR(), autoincrement=False, nullable=False),
        sa.Column("country", sa.VARCHAR(), autoincrement=False, nullable=False),
        sa.Column("dept_code", sa.VARCHAR(), autoincrement=False, nullable=False),
        sa.Column("region_code", sa.VARCHAR(), autoincrement=False, nullable=False),
        sa.Column("zip_code", sa.VARCHAR(), autoincrement=False, nullable=False),
        sa.Column("country_code", sa.VARCHAR(), autoincrement=False, nullable=False),
        sa.Column(
            "geo_lat",
            sa.NUMERIC(precision=11, scale=7),
            autoincrement=False,
            nullable=False,
        ),
        sa.Column(
            "geo_lng",
            sa.NUMERIC(precision=11, scale=7),
            autoincrement=False,
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["id"], ["cnt_base.id"], name="edt_editorial_id_fkey"),
        sa.ForeignKeyConstraint(
            ["publisher_id"],
            ["crp_organisation.id"],
            name="edt_editorial_publisher_id_fkey",
        ),
        sa.PrimaryKeyConstraint("id", name="edt_editorial_pkey"),
        postgresql_ignore_search_path=False,
    )
    op.create_table(
        "com_press_release",
        sa.Column("id", sa.BIGINT(), autoincrement=False, nullable=False),
        sa.Column("about", sa.VARCHAR(), autoincrement=False, nullable=False),
        sa.Column(
            "release_datetime",
            postgresql.TIMESTAMP(timezone=True),
            autoincrement=False,
            nullable=False,
        ),
        sa.Column(
            "embargo_datetime",
            postgresql.TIMESTAMP(timezone=True),
            autoincrement=False,
            nullable=False,
        ),
        sa.Column("image_url", sa.VARCHAR(), autoincrement=False, nullable=False),
        sa.Column("sector", sa.TEXT(), autoincrement=False, nullable=False),
        sa.Column("section", sa.TEXT(), autoincrement=False, nullable=False),
        sa.Column("genre", sa.TEXT(), autoincrement=False, nullable=False),
        sa.Column(
            "language", sa.VARCHAR(length=3), autoincrement=False, nullable=False
        ),
        sa.Column("topic", sa.TEXT(), autoincrement=False, nullable=False),
        sa.Column(
            "status",
            postgresql.ENUM(
                "DRAFT",
                "PRIVATE",
                "PENDING",
                "PUBLIC",
                "REJECTED",
                "EXPIRED",
                "ARCHIVED",
                "DELETED",
                name="publicationstatus",
            ),
            autoincrement=False,
            nullable=True,
        ),
        sa.Column(
            "published_at",
            postgresql.TIMESTAMP(timezone=True),
            autoincrement=False,
            nullable=True,
        ),
        sa.Column(
            "expired_at",
            postgresql.TIMESTAMP(timezone=True),
            autoincrement=False,
            nullable=True,
        ),
        sa.Column("publisher_id", sa.BIGINT(), autoincrement=False, nullable=True),
        sa.Column("_fts", sa.TEXT(), autoincrement=False, nullable=False),
        sa.Column("address", sa.VARCHAR(), autoincrement=False, nullable=False),
        sa.Column("city", sa.VARCHAR(), autoincrement=False, nullable=False),
        sa.Column("region", sa.VARCHAR(), autoincrement=False, nullable=False),
        sa.Column("departement", sa.VARCHAR(), autoincrement=False, nullable=False),
        sa.Column("country", sa.VARCHAR(), autoincrement=False, nullable=False),
        sa.Column("dept_code", sa.VARCHAR(), autoincrement=False, nullable=False),
        sa.Column("region_code", sa.VARCHAR(), autoincrement=False, nullable=False),
        sa.Column("zip_code", sa.VARCHAR(), autoincrement=False, nullable=False),
        sa.Column("country_code", sa.VARCHAR(), autoincrement=False, nullable=False),
        sa.Column(
            "geo_lat",
            sa.NUMERIC(precision=11, scale=7),
            autoincrement=False,
            nullable=False,
        ),
        sa.Column(
            "geo_lng",
            sa.NUMERIC(precision=11, scale=7),
            autoincrement=False,
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["id"], ["cnt_base.id"], name="com_press_release_id_fkey"
        ),
        sa.ForeignKeyConstraint(
            ["publisher_id"],
            ["crp_organisation.id"],
            name="com_press_release_publisher_id_fkey",
        ),
        sa.PrimaryKeyConstraint("id", name="com_press_release_pkey"),
    )
    op.create_table(
        "edt_visual",
        sa.Column("id", sa.BIGINT(), autoincrement=False, nullable=False),
        sa.Column("height", sa.INTEGER(), autoincrement=False, nullable=False),
        sa.Column("width", sa.INTEGER(), autoincrement=False, nullable=False),
        sa.Column("resolution", sa.VARCHAR(), autoincrement=False, nullable=False),
        sa.ForeignKeyConstraint(
            ["id"], ["edt_multimedia.id"], name="edt_visual_id_fkey"
        ),
        sa.PrimaryKeyConstraint("id", name="edt_visual_pkey"),
    )
    op.create_table(
        "edt_multimedia",
        sa.Column("id", sa.BIGINT(), autoincrement=False, nullable=False),
        sa.Column("format", sa.VARCHAR(), autoincrement=False, nullable=False),
        sa.Column("description", sa.VARCHAR(), autoincrement=False, nullable=False),
        sa.Column("blob", postgresql.BYTEA(), autoincrement=False, nullable=True),
        sa.Column("file_size", sa.INTEGER(), autoincrement=False, nullable=False),
        sa.ForeignKeyConstraint(
            ["id"], ["edt_editorial.id"], name="edt_multimedia_id_fkey"
        ),
        sa.PrimaryKeyConstraint("id", name="edt_multimedia_pkey"),
    )
    op.create_table(
        "edt_text",
        sa.Column("id", sa.BIGINT(), autoincrement=False, nullable=False),
        sa.ForeignKeyConstraint(["id"], ["edt_editorial.id"], name="edt_text_id_fkey"),
        sa.PrimaryKeyConstraint("id", name="edt_text_pkey"),
    )
    op.create_table(
        "wir_press_release",
        sa.Column("title", sa.VARCHAR(), autoincrement=False, nullable=False),
        sa.Column("content", sa.VARCHAR(), autoincrement=False, nullable=False),
        sa.Column("summary", sa.VARCHAR(), autoincrement=False, nullable=False),
        sa.Column(
            "status",
            postgresql.ENUM("DRAFT", "PUBLIC", "ARCHIVED", name="poststatus"),
            autoincrement=False,
            nullable=False,
        ),
        sa.Column(
            "published_at",
            postgresql.TIMESTAMP(timezone=True),
            autoincrement=False,
            nullable=True,
        ),
        sa.Column(
            "last_updated_at",
            postgresql.TIMESTAMP(timezone=True),
            autoincrement=False,
            nullable=True,
        ),
        sa.Column(
            "expires_at",
            postgresql.TIMESTAMP(timezone=True),
            autoincrement=False,
            nullable=True,
        ),
        sa.Column("publisher_id", sa.BIGINT(), autoincrement=False, nullable=True),
        sa.Column("image_id", sa.BIGINT(), autoincrement=False, nullable=True),
        sa.Column("id", sa.BIGINT(), autoincrement=True, nullable=False),
        sa.Column(
            "created_at",
            postgresql.TIMESTAMP(timezone=True),
            autoincrement=False,
            nullable=False,
        ),
        sa.Column(
            "modified_at",
            postgresql.TIMESTAMP(timezone=True),
            autoincrement=False,
            nullable=True,
        ),
        sa.Column(
            "deleted_at",
            postgresql.TIMESTAMP(timezone=True),
            autoincrement=False,
            nullable=True,
        ),
        sa.Column("owner_id", sa.INTEGER(), autoincrement=False, nullable=False),
        sa.Column("genre", sa.VARCHAR(), autoincrement=False, nullable=False),
        sa.Column("section", sa.VARCHAR(), autoincrement=False, nullable=False),
        sa.Column("topic", sa.VARCHAR(), autoincrement=False, nullable=False),
        sa.Column("sector", sa.VARCHAR(), autoincrement=False, nullable=False),
        sa.Column(
            "geo_localisation", sa.VARCHAR(), autoincrement=False, nullable=False
        ),
        sa.Column("language", sa.VARCHAR(), autoincrement=False, nullable=False),
        sa.Column("view_count", sa.INTEGER(), autoincrement=False, nullable=False),
        sa.Column("like_count", sa.INTEGER(), autoincrement=False, nullable=False),
        sa.Column("comment_count", sa.INTEGER(), autoincrement=False, nullable=False),
        sa.ForeignKeyConstraint(
            ["owner_id"], ["aut_user.id"], name="wir_press_release_owner_id_fkey"
        ),
        sa.ForeignKeyConstraint(
            ["publisher_id"],
            ["crp_organisation.id"],
            name="wir_press_release_publisher_id_fkey",
        ),
        sa.PrimaryKeyConstraint("id", name="wir_press_release_pkey"),
    )
    with op.batch_alter_table("frt_content", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_frt_content_object_id"))
        batch_op.drop_index(batch_op.f("ix_frt_content_newsroom_id"))

    op.drop_table("frt_content")
    # ### end Alembic commands ###
