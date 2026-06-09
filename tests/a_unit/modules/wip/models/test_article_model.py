# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Shape & pure-logic tests for the newsroom ``Article`` / ``Image`` models.

These tests pin the *contract* of the model definitions without touching a
database: column inventory, defaults, nullability, foreign-key targets,
mixin composition and ``__tablename__``. They also exercise the pure-Python
publication workflow (``can_publish`` / ``publish`` / ``unpublish``),
the boolean status properties, the timezone-aware ``is_expired`` branch and
the in-memory image carousel helpers.

Pinning the shape catches accidental schema drifts (renamed columns,
dropped defaults, lost FKs) in plain unit tests — fast feedback, no DB
needed.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.models.lifecycle import PublicationStatus
from app.models.mixins import IdMixin, LifeCycleMixin, Owned
from app.modules.wip.models.newsroom._base import (
    NewsMetadataMixin,
    NewsroomCommonMixin,
)
from app.modules.wip.models.newsroom.article import Article, Image

# ---------------------------------------------------------------------------
# Article — table shape
# ---------------------------------------------------------------------------


class TestArticleTableShape:
    """Pin the SQL-level contract of the ``Article`` model.

    Renaming a column or dropping a default would break templates, faker
    code and migrations elsewhere — these assertions force the change to
    be explicit.
    """

    def test_tablename(self):
        assert Article.__tablename__ == "nrm_article"

    def test_inherits_expected_mixins(self):
        """Article composes the newsroom mixins + Base."""
        mro_names = {cls.__name__ for cls in Article.__mro__}
        assert "NewsroomCommonMixin" in mro_names
        assert "NewsMetadataMixin" in mro_names
        assert "IdMixin" in mro_names
        assert "LifeCycleMixin" in mro_names
        assert "Owned" in mro_names
        # The mixin chain is reachable as real superclasses too.
        assert issubclass(Article, NewsroomCommonMixin)
        assert issubclass(Article, NewsMetadataMixin)
        assert issubclass(Article, IdMixin)
        assert issubclass(Article, LifeCycleMixin)
        assert issubclass(Article, Owned)

    @pytest.mark.parametrize(
        "col_name",
        [
            # Article-specific
            "chapo",
            "copyright",
            "date_parution_prevue",
            "date_publication_aip24",
            "status",
            "published_at",
            "expired_at",
            "address",
            "pays_zip_ville",
            "pays_zip_ville_detail",
            # From NewsroomCommonMixin
            "media_id",
            "commanditaire_id",
            "publisher_id",
            "titre",
            "brief",
            "numero_edition",
            "contenu",
            "type_contenu",
            "taille_contenu",
            # From IdMixin / LifeCycleMixin / Owned
            "id",
            "created_at",
            "modified_at",
            "deleted_at",
            "owner_id",
            # From NewsMetadataMixin
            "genre",
            "section",
            "topic",
            "sector",
            "geo_localisation",
            "language",
        ],
    )
    def test_expected_column_present(self, col_name: str):
        assert col_name in Article.__table__.columns

    @pytest.mark.parametrize(
        ("col_name", "expected_default"),
        [
            ("chapo", ""),
            ("copyright", ""),
            ("address", ""),
            ("pays_zip_ville", ""),
            ("pays_zip_ville_detail", ""),
            ("titre", ""),
            ("brief", ""),
            ("numero_edition", ""),
            ("contenu", ""),
            ("type_contenu", ""),
            ("taille_contenu", ""),
            ("genre", ""),
            ("section", ""),
            ("topic", ""),
            ("sector", ""),
            ("geo_localisation", ""),
            ("language", "fr"),
        ],
    )
    def test_scalar_string_defaults(self, col_name: str, expected_default: str):
        """String columns must have stable defaults — UI relies on them."""
        col = Article.__table__.columns[col_name]
        assert col.default is not None
        assert col.default.arg == expected_default

    def test_status_default_is_draft(self):
        col = Article.__table__.columns["status"]
        assert col.default is not None
        assert col.default.arg == PublicationStatus.DRAFT

    @pytest.mark.parametrize(
        "col_name",
        ["date_publication_aip24", "published_at", "expired_at", "publisher_id"],
    )
    def test_nullable_columns(self, col_name: str):
        assert Article.__table__.columns[col_name].nullable is True

    @pytest.mark.parametrize(
        "col_name",
        [
            "chapo",
            "copyright",
            "date_parution_prevue",
            "status",
            "titre",
            "contenu",
            "media_id",
            "commanditaire_id",
            "owner_id",
            "language",
        ],
    )
    def test_not_nullable_columns(self, col_name: str):
        assert Article.__table__.columns[col_name].nullable is False

    @pytest.mark.parametrize(
        ("col_name", "expected_table"),
        [
            ("media_id", "crp_organisation"),
            ("commanditaire_id", "aut_user"),
            ("publisher_id", "crp_organisation"),
            ("owner_id", "aut_user"),
        ],
    )
    def test_foreign_key_targets(self, col_name: str, expected_table: str):
        col = Article.__table__.columns[col_name]
        fks = list(col.foreign_keys)
        assert len(fks) == 1
        assert fks[0].column.table.name == expected_table


# ---------------------------------------------------------------------------
# Image — table shape
# ---------------------------------------------------------------------------


class TestImageTableShape:
    """Pin the ``Image`` table contract — including the CASCADE FK to Article.

    A regression here (e.g. dropping CASCADE) would orphan rows when an
    article is deleted, so this is worth pinning.
    """

    def test_tablename(self):
        assert Image.__tablename__ == "nrm_image"

    def test_inherits_expected_mixins(self):
        assert issubclass(Image, IdMixin)
        assert issubclass(Image, LifeCycleMixin)
        assert issubclass(Image, Owned)

    @pytest.mark.parametrize(
        "col_name",
        [
            "content",
            "article_id",
            "caption",
            "copyright",
            "position",
            "id",
            "created_at",
            "modified_at",
            "deleted_at",
            "owner_id",
        ],
    )
    def test_expected_column_present(self, col_name: str):
        assert col_name in Image.__table__.columns

    def test_position_default_is_zero(self):
        col = Image.__table__.columns["position"]
        assert col.default is not None
        assert col.default.arg == 0

    @pytest.mark.parametrize(
        ("col_name", "expected_default"),
        [("caption", ""), ("copyright", "")],
    )
    def test_string_defaults(self, col_name: str, expected_default: str):
        col = Image.__table__.columns[col_name]
        assert col.default is not None
        assert col.default.arg == expected_default

    def test_content_is_nullable(self):
        assert Image.__table__.columns["content"].nullable is True

    def test_article_fk_cascade(self):
        """Image -> Article FK must cascade on delete."""
        col = Image.__table__.columns["article_id"]
        fks = list(col.foreign_keys)
        assert len(fks) == 1
        assert fks[0].column.table.name == "nrm_article"
        assert fks[0].ondelete == "CASCADE"
        assert col.nullable is False


# ---------------------------------------------------------------------------
# Publication workflow — pure Python logic
# ---------------------------------------------------------------------------


class _StubArticle:
    """Duck-typed stand-in that exposes Article's pure-Python methods.

    We deliberately avoid instantiating ``Article`` (which would trigger
    SQLAlchemy state setup and require a session); instead we copy the
    pure-Python methods/properties onto this class so ``self.foo()``
    dispatch works just like on a real instance.
    """

    # Bind Article's pure-Python methods so internal ``self.x()`` calls work.
    can_publish = Article.can_publish
    publish = Article.publish
    can_unpublish = Article.can_unpublish
    unpublish = Article.unpublish
    get_image = Article.get_image
    add_image = Article.add_image
    delete_image = Article.delete_image
    update_image_positions = Article.update_image_positions
    sorted_images = Article.sorted_images
    is_draft = Article.is_draft
    is_public = Article.is_public
    is_expired = Article.is_expired

    def __init__(
        self,
        *,
        status: PublicationStatus = PublicationStatus.DRAFT,
        titre: str = "Un titre",
        contenu: str = "Du contenu",
        published_at: datetime | None = None,
        expired_at: datetime | None = None,
        images: list[Image] | None = None,
    ) -> None:
        self.status = status
        self.titre = titre
        self.contenu = contenu
        self.published_at = published_at
        self.expired_at = expired_at
        self.publisher_id: int | None = None
        self.images: list[Image] = images if images is not None else []


def _call(method_name: str, stub: _StubArticle, *args, **kwargs):
    """Invoke an Article instance method against a stand-in stub."""
    return getattr(Article, method_name)(stub, *args, **kwargs)


class TestPublicationWorkflow:
    """Pure publication state-machine — no DB, no time mocking required."""

    def test_can_publish_when_draft(self):
        assert _call("can_publish", _StubArticle()) is True

    @pytest.mark.parametrize(
        "status",
        [
            PublicationStatus.PUBLIC,
            PublicationStatus.ARCHIVED,
            PublicationStatus.EXPIRED,
            PublicationStatus.REJECTED,
        ],
    )
    def test_cannot_publish_when_not_draft(self, status: PublicationStatus):
        assert _call("can_publish", _StubArticle(status=status)) is False

    def test_publish_transitions_to_public_and_sets_timestamp(self):
        stub = _StubArticle()
        _call("publish", stub)
        assert stub.status == PublicationStatus.PUBLIC
        assert stub.published_at is not None

    def test_publish_preserves_existing_published_at(self):
        original = datetime(2024, 1, 1, tzinfo=UTC)
        stub = _StubArticle(published_at=original)
        _call("publish", stub)
        assert stub.published_at == original

    def test_publish_sets_publisher_id_when_given(self):
        stub = _StubArticle()
        _call("publish", stub, publisher_id=42)
        assert stub.publisher_id == 42

    def test_publish_ignores_falsy_publisher_id(self):
        stub = _StubArticle()
        _call("publish", stub, publisher_id=0)
        assert stub.publisher_id is None

    def test_publish_raises_when_not_draft(self):
        stub = _StubArticle(status=PublicationStatus.PUBLIC)
        with pytest.raises(ValueError, match="not in DRAFT"):
            _call("publish", stub)

    @pytest.mark.parametrize("bad_titre", ["", "   "])
    def test_publish_raises_on_blank_titre(self, bad_titre: str):
        stub = _StubArticle(titre=bad_titre)
        with pytest.raises(ValueError, match="titre is required"):
            _call("publish", stub)

    @pytest.mark.parametrize("bad_contenu", ["", "   "])
    def test_publish_raises_on_blank_contenu(self, bad_contenu: str):
        stub = _StubArticle(contenu=bad_contenu)
        with pytest.raises(ValueError, match="contenu is required"):
            _call("publish", stub)

    def test_can_unpublish_only_when_public(self):
        assert _call("can_unpublish", _StubArticle()) is False
        public = _StubArticle(status=PublicationStatus.PUBLIC)
        assert _call("can_unpublish", public) is True

    def test_unpublish_returns_to_draft(self):
        stub = _StubArticle(status=PublicationStatus.PUBLIC)
        _call("unpublish", stub)
        assert stub.status == PublicationStatus.DRAFT

    def test_unpublish_raises_when_not_public(self):
        stub = _StubArticle()
        with pytest.raises(ValueError, match="not PUBLIC"):
            _call("unpublish", stub)


# ---------------------------------------------------------------------------
# Boolean status properties
# ---------------------------------------------------------------------------


class TestStatusProperties:
    """``is_draft`` / ``is_public`` / ``is_expired`` drive template rendering."""

    def test_is_draft_true_for_draft(self):
        assert Article.is_draft.fget(_StubArticle()) is True

    def test_is_draft_false_for_public(self):
        stub = _StubArticle(status=PublicationStatus.PUBLIC)
        assert Article.is_draft.fget(stub) is False

    def test_is_public_true_for_public(self):
        stub = _StubArticle(status=PublicationStatus.PUBLIC)
        assert Article.is_public.fget(stub) is True

    def test_is_public_false_for_draft(self):
        assert Article.is_public.fget(_StubArticle()) is False

    def test_is_expired_false_when_no_expired_at(self):
        assert Article.is_expired.fget(_StubArticle()) is False

    def test_is_expired_true_when_past(self):
        past = datetime.now(UTC) - timedelta(days=1)
        stub = _StubArticle(expired_at=past)
        assert Article.is_expired.fget(stub) is True

    def test_is_expired_false_when_future(self):
        future = datetime.now(UTC) + timedelta(days=1)
        stub = _StubArticle(expired_at=future)
        assert Article.is_expired.fget(stub) is False

    def test_is_expired_handles_naive_datetime(self):
        """A naive datetime in the past must be treated as UTC, not crash."""
        naive_past = datetime.utcnow() - timedelta(days=1)  # noqa: DTZ003
        stub = _StubArticle(expired_at=naive_past)
        assert Article.is_expired.fget(stub) is True


# ---------------------------------------------------------------------------
# Image carousel helpers
# ---------------------------------------------------------------------------


class _StubImage:
    """Minimal duck for Image — only ``id`` and ``position`` are used."""

    def __init__(self, *, id: int, position: int = 0) -> None:
        self.id = id
        self.position = position


class TestImageCarousel:
    """Pure in-memory list manipulation — no relationship loading needed."""

    def test_get_image_returns_match(self):
        images = [_StubImage(id=1), _StubImage(id=2)]
        stub = _StubArticle(images=images)
        assert _call("get_image", stub, 2) is images[1]

    def test_get_image_returns_none_when_missing(self):
        stub = _StubArticle(images=[_StubImage(id=1)])
        assert _call("get_image", stub, 999) is None

    def test_sorted_images_orders_by_position(self):
        images = [
            _StubImage(id=1, position=2),
            _StubImage(id=2, position=0),
            _StubImage(id=3, position=1),
        ]
        stub = _StubArticle(images=images)
        ordered = Article.sorted_images.fget(stub)
        assert [img.id for img in ordered] == [2, 3, 1]

    def test_add_image_appends_and_sets_position(self):
        existing = [_StubImage(id=1, position=0)]
        stub = _StubArticle(images=existing)
        new_img = _StubImage(id=2)
        _call("add_image", stub, new_img)
        assert stub.images[-1] is new_img
        assert new_img.position == 1

    def test_delete_image_removes_and_reindexes(self):
        a, b, c = (
            _StubImage(id=1, position=0),
            _StubImage(id=2, position=1),
            _StubImage(id=3, position=2),
        )
        stub = _StubArticle(images=[a, b, c])
        _call("delete_image", stub, b)
        assert b not in stub.images
        # remaining positions must be contiguous starting at 0
        assert sorted(img.position for img in stub.images) == [0, 1]

    def test_update_image_positions_is_idempotent(self):
        images = [
            _StubImage(id=1, position=5),
            _StubImage(id=2, position=3),
        ]
        stub = _StubArticle(images=images)
        _call("update_image_positions", stub)
        positions = sorted(img.position for img in stub.images)
        assert positions == [0, 1]


# ---------------------------------------------------------------------------
# Image pure-python properties
# ---------------------------------------------------------------------------


class _StubImageWithArticle:
    def __init__(self, *, position: int, total: int) -> None:
        self.position = position
        # ``is_last`` only consults ``len(self.article.images)``.
        self.article = type("A", (), {"images": list(range(total))})()


class TestImageProperties:
    """``is_first`` / ``is_last`` — used by templates to render arrows."""

    def test_is_first_true_at_position_zero(self):
        stub = _StubImageWithArticle(position=0, total=3)
        assert Image.is_first.fget(stub) is True

    def test_is_first_false_otherwise(self):
        stub = _StubImageWithArticle(position=1, total=3)
        assert Image.is_first.fget(stub) is False

    def test_is_last_true_at_final_index(self):
        stub = _StubImageWithArticle(position=2, total=3)
        assert Image.is_last.fget(stub) is True

    def test_is_last_false_otherwise(self):
        stub = _StubImageWithArticle(position=0, total=3)
        assert Image.is_last.fget(stub) is False
