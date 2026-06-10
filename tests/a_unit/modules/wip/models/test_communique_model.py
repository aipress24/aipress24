# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Unit tests pinning the *shape* and pure logic of `Communique` and
`ComImage` at `app.modules.wip.models.comroom.communique`.

No DB. We introspect SQLAlchemy metadata for the column inventory,
defaults, FK + ondelete (CASCADE on `crm_image.communique_id`), and
exercise the publication workflow guard rails (`can_publish`,
`publish`, `unpublish`) — they encode the « no double publish, no
skipping titre/contenu, no breaking embargo » business rules the PR
desk relies on. Pure properties (`is_draft`, `is_public`,
`is_embargoed`, `is_expired`, `title`, `sorted_images`, `is_first`,
`is_last`, `url`) are exercised through a stand-in that copies the
methods from `Communique` so we don't pay for SQLAlchemy's
`InstrumentedAttribute` machinery.

No mocks, no patches: `url` delegation is verified by passing a real
`FileObject` and asserting the produced `/media/...` URL.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import ClassVar

import pytest
import sqlalchemy as sa
from advanced_alchemy.types import FileObject
from sqlalchemy import inspect as sa_inspect

from app.models.lifecycle import PublicationStatus
from app.modules.wip.models.comroom.communique import ComImage, Communique


def _column(model, name):
    """Fetch a column from a mapped class without instantiating a row."""
    return model.__table__.columns[name]


class TestCommuniqueClassShape:
    """Pin the table name and mixin contributions — losing `Owned` /
    `LifeCycleMixin` would silently drop `owner_id` / `created_at`
    which every comroom query relies on."""

    def test_tablename(self):
        assert Communique.__tablename__ == "crm_communique"

    def test_is_sqlalchemy_mapped(self):
        mapper = sa_inspect(Communique)
        assert mapper is not None and mapper.class_ is Communique

    @pytest.mark.parametrize(
        "col_name",
        ["created_at", "modified_at", "deleted_at", "owner_id"],
    )
    def test_mixin_columns_present(self, col_name):
        assert col_name in Communique.__table__.columns

    def test_has_bigint_id_pk(self):
        """`IdMixin` supplies a BigInteger PK — INT would collide
        with the Snowflake generator."""
        col = _column(Communique, "id")
        assert col.primary_key is True
        assert isinstance(col.type, sa.BigInteger)


class TestCommuniqueColumns:
    """The column set is the table's contract with the rest of the
    codebase. Pin it — every comroom form / view reads at least
    one of these by name."""

    EXPECTED_COLUMNS: ClassVar[set[str]] = {
        "id",
        "created_at",
        "modified_at",
        "deleted_at",
        "owner_id",
        "chapo",
        "contenu",
        "status",
        "embargoed_until",
        "published_at",
        "expired_at",
        "publisher_id",
        "titre",
        "genre",
        "section",
        "topic",
        "sector",
        "geo_localisation",
        "language",
        "address",
        "pays_zip_ville",
        "pays_zip_ville_detail",
    }

    def test_expected_columns_all_present(self):
        actual = set(Communique.__table__.columns.keys())
        missing = self.EXPECTED_COLUMNS - actual
        assert not missing, f"Missing columns on Communique: {missing}"

    @pytest.mark.parametrize(
        "col_name",
        ["embargoed_until", "published_at", "expired_at", "publisher_id"],
    )
    def test_optional_columns_nullable(self, col_name):
        """A freshly created draft has no embargo / publication date /
        expiration / publisher — all must accept NULL."""
        assert _column(Communique, col_name).nullable is True

    @pytest.mark.parametrize(
        ("col_name", "default_value"),
        [
            ("chapo", ""),
            ("contenu", ""),
            ("titre", ""),
            ("genre", ""),
            ("section", ""),
            ("topic", ""),
            ("sector", ""),
            ("geo_localisation", ""),
            ("language", "fr"),  # primary comroom language
            ("address", ""),
            ("pays_zip_ville", ""),
            ("pays_zip_ville_detail", ""),
        ],
    )
    def test_string_column_defaults(self, col_name, default_value):
        """Strings default to `""` for safe `.strip()` / templating;
        `language` defaults to `fr`."""
        col = _column(Communique, col_name)
        assert col.default is not None
        assert col.default.arg == default_value


class TestStatusAndPublisherFK:
    """`status` defaults to DRAFT — new rows must NEVER auto-publish.
    `publisher_id` points at `crp_organisation` — comroom publishes
    on behalf of an org; pin so a rename catches here."""

    def test_status_column_uses_publication_status_enum(self):
        assert isinstance(_column(Communique, "status").type, sa.Enum)

    def test_status_default_is_draft(self):
        col = _column(Communique, "status")
        assert col.default is not None
        assert col.default.arg == PublicationStatus.DRAFT

    def test_publisher_fk_target(self):
        fks = list(_column(Communique, "publisher_id").foreign_keys)
        assert len(fks) == 1
        assert fks[0].column.name == "id"
        assert fks[0].column.table.name == "crp_organisation"

    def test_publisher_relationship_exists(self):
        rel = sa_inspect(Communique).relationships["publisher"]
        assert rel.mapper.class_.__name__ == "Organisation"


# ---------------------------------------------------------------------------
# Stand-in for pure-logic tests — copies methods off Communique
# without inheriting SQLAlchemy's instrumentation.
# ---------------------------------------------------------------------------


class _CommStub:
    def __init__(self, **kwargs):
        self.status = kwargs.get("status", PublicationStatus.DRAFT)
        self.titre = kwargs.get("titre", "")
        self.contenu = kwargs.get("contenu", "")
        self.embargoed_until = kwargs.get("embargoed_until")
        self.published_at = kwargs.get("published_at")
        self.expired_at = kwargs.get("expired_at")
        self.publisher_id = kwargs.get("publisher_id")
        self.images = kwargs.get("images", [])


# Lift functions / property descriptors verbatim — they only touch
# Python attributes, which the stub exposes as plain instance dict
# entries. No SQLAlchemy InstanceState required.
for _name in (
    "title",
    "is_draft",
    "is_public",
    "is_embargoed",
    "is_expired",
    "set_embargo",
    "can_publish",
    "publish",
    "can_unpublish",
    "unpublish",
    "get_image",
    "sorted_images",
    "add_image",
    "delete_image",
    "update_image_positions",
):
    setattr(_CommStub, _name, Communique.__dict__[_name])


def _comm_stub(**kwargs) -> _CommStub:
    return _CommStub(**kwargs)


class TestTitleAlias:
    """`title` is a back-compat alias for `titre` — generic table
    cells expect `.title`."""

    def test_title_returns_titre(self):
        assert _comm_stub(titre="X").title == "X"

    def test_title_empty_when_titre_empty(self):
        assert _comm_stub(titre="").title == ""


class TestStatusProperties:
    """`is_draft` / `is_public` drive list filters and template
    branches — only DRAFT is draft, only PUBLIC is public; pin so
    a new state (e.g. ARCHIVED) doesn't accidentally claim either."""

    def test_is_draft_only_for_draft_status(self):
        assert _comm_stub(status=PublicationStatus.DRAFT).is_draft is True
        assert _comm_stub(status=PublicationStatus.PUBLIC).is_draft is False

    def test_is_public_only_for_public_status(self):
        assert _comm_stub(status=PublicationStatus.PUBLIC).is_public is True
        assert _comm_stub(status=PublicationStatus.DRAFT).is_public is False

    @pytest.mark.parametrize(
        "status",
        [
            PublicationStatus.PRIVATE,
            PublicationStatus.PENDING,
            PublicationStatus.REJECTED,
            PublicationStatus.EXPIRED,
            PublicationStatus.ARCHIVED,
        ],
    )
    def test_other_states_are_neither(self, status):
        stub = _comm_stub(status=status)
        assert stub.is_draft is False
        assert stub.is_public is False


class TestEmbargoAndExpiredProperties:
    """`is_embargoed` gates early publication; `is_expired` flags
    content past its display window. Both fall back to assuming UTC
    for naive datetimes — pin so the fallback isn't removed."""

    def test_embargo_none_returns_false(self):
        assert _comm_stub(embargoed_until=None).is_embargoed is False

    def test_embargo_future_returns_true(self):
        future = datetime.now(UTC) + timedelta(hours=1)
        assert _comm_stub(embargoed_until=future).is_embargoed is True

    def test_embargo_past_returns_false(self):
        past = datetime.now(UTC) - timedelta(hours=1)
        assert _comm_stub(embargoed_until=past).is_embargoed is False

    def test_embargo_naive_future_treated_as_utc(self):
        future_naive = datetime.now(UTC).replace(tzinfo=None) + timedelta(hours=1)
        assert _comm_stub(embargoed_until=future_naive).is_embargoed is True

    def test_expired_none_returns_false(self):
        assert _comm_stub(expired_at=None).is_expired is False

    def test_expired_past_returns_true(self):
        past = datetime.now(UTC) - timedelta(hours=1)
        assert _comm_stub(expired_at=past).is_expired is True

    def test_expired_future_returns_false(self):
        future = datetime.now(UTC) + timedelta(hours=1)
        assert _comm_stub(expired_at=future).is_expired is False

    def test_expired_naive_past_treated_as_utc(self):
        past_naive = datetime.now(UTC).replace(tzinfo=None) - timedelta(hours=1)
        assert _comm_stub(expired_at=past_naive).is_expired is True


class TestSetEmbargoAndCanPublish:
    """`set_embargo` is a thin setter — pin set + clear. `can_publish`
    is the precondition checked by the publish button: only DRAFT
    is allowed (re-publishing PUBLIC is not idempotent)."""

    def test_set_embargo_assigns(self):
        stub = _comm_stub()
        when = datetime.now(UTC) + timedelta(days=1)
        stub.set_embargo(when)
        assert stub.embargoed_until == when

    def test_set_embargo_none_clears(self):
        stub = _comm_stub(embargoed_until=datetime.now(UTC))
        stub.set_embargo(None)
        assert stub.embargoed_until is None

    def test_can_publish_when_draft(self):
        assert _comm_stub(status=PublicationStatus.DRAFT).can_publish() is True

    @pytest.mark.parametrize(
        "status",
        [
            PublicationStatus.PUBLIC,
            PublicationStatus.PRIVATE,
            PublicationStatus.PENDING,
            PublicationStatus.ARCHIVED,
        ],
    )
    def test_cannot_publish_from_non_draft(self, status):
        assert _comm_stub(status=status).can_publish() is False


class TestPublish:
    """The most important business operation. Pin its guard rails :
    DRAFT-only, requires titre + contenu, blocks on active embargo,
    sets `published_at` once. Each guard prevents a distinct
    failure mode in production."""

    def test_publish_sets_public_and_published_at(self):
        stub = _comm_stub(titre="t", contenu="c")
        stub.publish()
        assert stub.status == PublicationStatus.PUBLIC
        assert stub.published_at is not None

    def test_publish_preserves_existing_published_at(self):
        """Re-publishing must not overwrite the original date."""
        original = datetime(2020, 1, 1, tzinfo=UTC)
        stub = _comm_stub(titre="t", contenu="c", published_at=original)
        stub.publish()
        assert stub.published_at == original

    def test_publish_sets_publisher_id_when_provided(self):
        stub = _comm_stub(titre="t", contenu="c")
        stub.publish(publisher_id=42)
        assert stub.publisher_id == 42

    def test_publish_falsy_publisher_id_does_not_overwrite(self):
        """`if publisher_id:` is falsy for 0 — pin so a refactor to
        `is not None` doesn't silently change behaviour."""
        stub = _comm_stub(titre="t", contenu="c", publisher_id=None)
        stub.publish(publisher_id=0)
        assert stub.publisher_id is None

    @pytest.mark.parametrize(
        "status",
        [PublicationStatus.PUBLIC, PublicationStatus.ARCHIVED],
    )
    def test_publish_raises_when_not_draft(self, status):
        stub = _comm_stub(status=status, titre="t", contenu="c")
        with pytest.raises(ValueError, match="not in DRAFT"):
            stub.publish()

    @pytest.mark.parametrize("titre", ["", "   ", "\t\n"])
    def test_publish_raises_when_titre_blank(self, titre):
        with pytest.raises(ValueError, match="titre is required"):
            _comm_stub(titre=titre, contenu="c").publish()

    @pytest.mark.parametrize("contenu", ["", "   ", "\t\n"])
    def test_publish_raises_when_contenu_blank(self, contenu):
        with pytest.raises(ValueError, match="contenu is required"):
            _comm_stub(titre="t", contenu=contenu).publish()

    def test_publish_raises_when_under_embargo(self):
        future = datetime.now(UTC) + timedelta(hours=1)
        stub = _comm_stub(titre="t", contenu="c", embargoed_until=future)
        with pytest.raises(ValueError, match="under embargo"):
            stub.publish()

    def test_publish_succeeds_when_embargo_expired(self):
        past = datetime.now(UTC) - timedelta(hours=1)
        stub = _comm_stub(titre="t", contenu="c", embargoed_until=past)
        stub.publish()
        assert stub.status == PublicationStatus.PUBLIC


class TestUnpublish:
    """Inverse of `publish` — only allowed from PUBLIC, returns to
    DRAFT. Pin guard so DRAFT->DRAFT is rejected (a no-op that
    should be reported as an error)."""

    def test_can_unpublish_only_when_public(self):
        assert _comm_stub(status=PublicationStatus.PUBLIC).can_unpublish() is True
        assert _comm_stub(status=PublicationStatus.DRAFT).can_unpublish() is False

    def test_unpublish_returns_to_draft(self):
        stub = _comm_stub(status=PublicationStatus.PUBLIC)
        stub.unpublish()
        assert stub.status == PublicationStatus.DRAFT

    def test_unpublish_from_non_public_raises(self):
        stub = _comm_stub(status=PublicationStatus.DRAFT)
        with pytest.raises(ValueError, match="not PUBLIC"):
            stub.unpublish()


# ---------------------------------------------------------------------------
# Image management — pure list ops
# ---------------------------------------------------------------------------


class _ImageStub:
    def __init__(self, id_: int, position: int = 0):
        self.id = id_
        self.position = position


class TestImageManagement:
    """`get_image`, `add_image`, `delete_image`, `sorted_images`,
    `update_image_positions` operate on the in-memory `images`
    list. Pin position re-indexing so deleting from the middle
    doesn't leave gaps."""

    def test_get_image_by_id(self):
        img1, img2 = _ImageStub(1), _ImageStub(2)
        stub = _comm_stub(images=[img1, img2])
        assert stub.get_image(2) is img2
        assert stub.get_image(999) is None

    def test_sorted_images_orders_by_position(self):
        a = _ImageStub(1, position=2)
        b = _ImageStub(2, position=0)
        c = _ImageStub(3, position=1)
        result = _comm_stub(images=[a, b, c]).sorted_images
        assert [img.id for img in result] == [2, 3, 1]

    def test_add_image_assigns_position_at_tail(self):
        existing = _ImageStub(1, position=0)
        stub = _comm_stub(images=[existing])
        new = _ImageStub(2)
        stub.add_image(new)
        assert new.position == 1
        assert new in stub.images

    def test_add_image_to_empty_list_position_zero(self):
        stub = _comm_stub(images=[])
        new = _ImageStub(1)
        stub.add_image(new)
        assert new.position == 0

    def test_delete_image_reindexes(self):
        """Deleting from the middle must compact remaining
        positions — gaps would break the carousel ordering."""
        a = _ImageStub(1, position=0)
        b = _ImageStub(2, position=1)
        c = _ImageStub(3, position=2)
        stub = _comm_stub(images=[a, b, c])
        stub.delete_image(b)
        assert b not in stub.images
        assert (a.position, c.position) == (0, 1)

    def test_update_image_positions_compacts(self):
        a = _ImageStub(1, position=5)
        b = _ImageStub(2, position=10)
        c = _ImageStub(3, position=15)
        _comm_stub(images=[a, b, c]).update_image_positions()
        assert [a.position, b.position, c.position] == [0, 1, 2]


# ---------------------------------------------------------------------------
# ComImage
# ---------------------------------------------------------------------------


class TestComImageClassShape:
    """`ComImage` rows are tightly coupled to their parent
    communique. Pin tablename + FK + ON DELETE CASCADE so deleting
    a communique truly removes its carousel images."""

    EXPECTED_COLUMNS: ClassVar[set[str]] = {
        "id",
        "created_at",
        "modified_at",
        "deleted_at",
        "owner_id",
        "content",
        "communique_id",
        "caption",
        "copyright",
        "position",
    }

    def test_tablename(self):
        assert ComImage.__tablename__ == "crm_image"

    def test_expected_columns_all_present(self):
        actual = set(ComImage.__table__.columns.keys())
        missing = self.EXPECTED_COLUMNS - actual
        assert not missing, f"Missing columns on ComImage: {missing}"

    def test_communique_id_not_nullable(self):
        assert _column(ComImage, "communique_id").nullable is False

    def test_communique_id_fk_targets_communique(self):
        col = _column(ComImage, "communique_id")
        fks = list(col.foreign_keys)
        assert len(fks) == 1
        assert fks[0].column.table.name == "crm_communique"
        assert fks[0].column.name == "id"

    def test_communique_id_fk_cascade_on_delete(self):
        """Deleting the parent must wipe the children, otherwise
        the carousel leaks rows."""
        col = _column(ComImage, "communique_id")
        fk = next(iter(col.foreign_keys))
        assert fk.ondelete == "CASCADE"

    @pytest.mark.parametrize(
        ("col_name", "default_value"),
        [("caption", ""), ("copyright", ""), ("position", 0)],
    )
    def test_defaults(self, col_name, default_value):
        col = _column(ComImage, col_name)
        assert col.default is not None
        assert col.default.arg == default_value

    def test_content_is_nullable(self):
        """An image row can exist briefly without its blob
        (upload pending)."""
        assert _column(ComImage, "content").nullable is True


class TestComImageProperties:
    """`is_first` / `is_last` drive arrow-button visibility in the
    carousel editor; `url` proxies to `media_url`. We use a real
    `FileObject` here to verify URL composition end-to-end without
    patching."""

    def test_is_first(self):
        assert ComImage.is_first.fget(_ImageStub(1, position=0)) is True
        assert ComImage.is_first.fget(_ImageStub(1, position=3)) is False

    def test_is_last_when_position_equals_last_index(self):
        parent = _comm_stub(images=[_ImageStub(i) for i in range(3)])

        class _Img:
            position = 2
            communique = parent

        assert ComImage.is_last.fget(_Img()) is True

    def test_is_last_false_when_not_at_end(self):
        parent = _comm_stub(images=[_ImageStub(i) for i in range(3)])

        class _Img:
            position = 1
            communique = parent

        assert ComImage.is_last.fget(_Img()) is False

    def test_url_returns_media_path_for_stored_object(self):
        """A FileObject with a `to_filename` should produce the
        `/media/{path}` URL form."""
        file_obj = FileObject(
            backend="s3",
            filename="photo.jpg",
            to_filename="deadbeef.jpg",
        )

        class _Img:
            content = file_obj

        assert ComImage.url.fget(_Img()) == "/media/deadbeef.jpg"

    def test_url_returns_placeholder_when_content_missing(self):
        """No FileObject → broken-image placeholder; templates rely
        on this to render an `<img>` tag without crashing."""

        class _Img:
            content = None

        assert ComImage.url.fget(_Img()) == "/static/img/gray-texture.png"
