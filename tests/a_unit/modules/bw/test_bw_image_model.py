# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Unit tests pinning the *shape* and *pure logic* of the `BWImage`
SQLAlchemy mapped class at
`app.modules.bw.bw_activation.models.business_wall`.

These tests do NOT touch a database. They introspect SQLAlchemy
metadata to lock in:

- Table name (used by Alembic migrations and downstream raw SQL).
- The set of columns + their nullability + their default values.
- Foreign key on `business_wall_id` with ON DELETE CASCADE — when a
  Business Wall is deleted, its gallery images must vanish with it,
  otherwise we leak S3 references to orphaned rows.
- The class inherits from `UUIDAuditBase` (UUID PK + `created_at` /
  `updated_at` audit columns are part of the contract).
- The `url` property formats `/bw/<bw_id>/images/<image_id>` — this
  is the public route shape that templates and tests grep for.
- The `signed_url` method falls back to a transparent-square placeholder
  when `content` is None (defensive against half-populated rows), and
  delegates to `FileObject.sign` with the right kwargs otherwise.

DB-bound behaviour (constraint violation, defaults at INSERT time,
real S3 signing) is covered by `b_integration` tests, not here.
"""

from __future__ import annotations

import inspect
from typing import ClassVar

import pytest
from advanced_alchemy.base import UUIDAuditBase
from sqlalchemy import inspect as sa_inspect

from app.modules.bw.bw_activation.models.business_wall import BWImage


def _column(model, name):
    """Helper — fetch a column from a mapped class without instantiating
    a row."""
    return model.__table__.columns[name]


class TestBWImageClassShape:
    """The class must be a SQLAlchemy mapped class inheriting from
    `UUIDAuditBase`. That parent supplies the UUID `id` primary key and
    the audit columns the gallery UI relies on for ordering and
    « last-modified » badges.
    """

    def test_inherits_from_uuid_audit_base(self):
        """Pin the parent so a refactor to a different base catches
        here, not at first INSERT against a broken table."""
        assert issubclass(BWImage, UUIDAuditBase)

    def test_tablename(self):
        """Hard-coded `__tablename__` is referenced by Alembic
        migrations — renaming it without a migration would silently
        break SELECTs and orphan the existing rows."""
        assert BWImage.__tablename__ == "bw_image"

    def test_is_sqlalchemy_mapped(self):
        """`sa_inspect` succeeds only on mapped classes — a defensive
        gate against a refactor that turns this into a plain dataclass."""
        mapper = sa_inspect(BWImage)
        assert mapper is not None
        assert mapper.class_ is BWImage


class TestBWImageColumns:
    """The column set is the table's contract with the rest of the
    codebase. Every gallery query, every upload handler, every template
    reads at least one of these columns by name."""

    EXPECTED_COLUMNS = frozenset(
        {
            # From UUIDAuditBase
            "id",
            "created_at",
            "updated_at",
            # From BWImage itself
            "content",
            "business_wall_id",
            "caption",
            "copyright",
            "position",
        }
    )

    def test_expected_columns_all_present(self):
        """At minimum, every name the BW gallery code reads must exist.
        We allow extras (e.g. `sa_orm_sentinel` from
        advanced-alchemy)."""
        actual = set(BWImage.__table__.columns.keys())
        missing = self.EXPECTED_COLUMNS - actual
        assert not missing, f"Missing columns on BWImage: {missing}"

    def test_business_wall_id_is_not_nullable(self):
        """Every gallery image MUST belong to a Business Wall — a
        dangling image (no parent) is meaningless and the CASCADE FK
        relies on this NOT NULL invariant."""
        assert _column(BWImage, "business_wall_id").nullable is False

    def test_content_is_nullable(self):
        """The `content` (S3 file) is nullable on purpose — a row can
        exist with just a caption while the upload is pending or after
        an admin scrubs the file. `signed_url` handles the None case."""
        assert _column(BWImage, "content").nullable is True


class TestBWImageDefaults:
    """The column-level defaults define what a freshly-built BWImage
    looks like before the user has filled anything in. Pin them so
    a refactor that silently swaps `default=""` for `default=None`
    doesn't break templates that assume strings."""

    @pytest.mark.parametrize(
        ("col_name", "expected"),
        [
            ("caption", ""),
            ("copyright", ""),
            ("position", 0),
        ],
    )
    def test_scalar_column_default(self, col_name, expected):
        """`caption` / `copyright` default to empty strings (not None)
        so templates can safely call `.strip()` etc. `position`
        defaults to 0 so the first image inserted lands at the front."""
        col = _column(BWImage, col_name)
        assert col.default is not None
        assert col.default.arg == expected


class TestBWImageForeignKey:
    """Pin the FK target + ondelete behaviour. ON DELETE CASCADE on
    `business_wall_id` is critical — deleting a Business Wall must
    clear its gallery rows, otherwise we leak references to S3 files
    nothing points at anymore."""

    def test_business_wall_fk_target(self):
        """FK must point at `bw_business_wall.id` — pin the table and
        column name so a rename of the BW table is caught at test
        time, not at Alembic-migration time."""
        col = _column(BWImage, "business_wall_id")
        fks = list(col.foreign_keys)
        assert len(fks) == 1
        assert fks[0].column.table.name == "bw_business_wall"
        assert fks[0].column.name == "id"

    def test_business_wall_fk_cascade_on_delete(self):
        """ON DELETE CASCADE is a hard requirement — without it,
        deleting a BW would either fail (FK violation) or leave orphan
        rows referencing nothing."""
        col = _column(BWImage, "business_wall_id")
        fk = next(iter(col.foreign_keys))
        assert fk.ondelete == "CASCADE"


class TestBWImageRelationship:
    """Pin the ORM-level relationship + the `backref` name. The backref
    `bw_images` is read by `BusinessWall.sorted_bw_images`,
    `add_bw_image`, `get_bw_image`, etc. — renaming it would break
    the parent model silently."""

    def test_business_wall_relationship_exists(self):
        mapper = sa_inspect(BWImage)
        assert "business_wall" in mapper.relationships
        rel = mapper.relationships["business_wall"]
        assert rel.mapper.class_.__name__ == "BusinessWall"

    def test_backref_name_is_bw_images(self):
        """`BusinessWall.bw_images` is the documented accessor — pin it
        so it can't drift to `images` or similar."""
        bw_mapper = sa_inspect(
            sa_inspect(BWImage).relationships["business_wall"].mapper.class_
        )
        assert "bw_images" in bw_mapper.relationships


class TestUrlProperty:
    """`BWImage.url` is the public route the template uses to serve a
    gallery image. Its exact string shape is part of the URL contract
    — if it changes, every `<img src>` in templates would 404."""

    def test_url_format(self):
        """Pin the literal `/bw/<bw_id>/images/<image_id>` shape using
        a stand-in instead of building a real ORM row."""

        class _StandIn:
            business_wall_id = "bw-42"
            id = "img-7"

        rendered = BWImage.url.fget(_StandIn())  # type: ignore[arg-type]
        assert rendered == "/bw/bw-42/images/img-7"

    def test_url_uses_business_wall_id_not_relationship(self):
        """The property reads `self.business_wall_id` directly (the FK
        column), NOT `self.business_wall.id`. That matters because a
        detached / pre-flush row may not have its relationship loaded
        but always has its FK value once the parent is assigned."""

        class _StandIn:
            business_wall_id = "from-column"
            id = "img-1"
            # Note: no `business_wall` attribute — `url` must not need it
            business_wall = None  # would crash if .url touched .id on it

        rendered = BWImage.url.fget(_StandIn())  # type: ignore[arg-type]
        assert "from-column" in rendered
        assert rendered.startswith("/bw/")


class TestSignedUrlMethod:
    """`signed_url` is the production path used to render gallery
    images directly from S3. Its behaviour matters in two regimes:
    1. `content is None` → fall back to a static placeholder (defensive
       — a half-populated row must not crash the template).
    2. `content is set` → delegate to `FileObject.sign` with the
       correct kwargs (`expires_in=..., for_upload=False`)."""

    def test_signature_default_expires_in_is_3600(self):
        """Pin the default expiration window (1h). Some callers omit
        the arg — they implicitly rely on this default."""
        sig = inspect.signature(BWImage.signed_url)
        assert sig.parameters["expires_in"].default == 3600

    def test_returns_placeholder_when_content_is_none(self):
        """If `content` is None, the method MUST return the
        transparent-square placeholder, NOT crash and NOT return an
        empty string (templates render the result as `<img src>`)."""

        class _StandIn:
            content = None
            id = "img-1"

        result = BWImage.signed_url(_StandIn())  # type: ignore[arg-type]
        assert result == "/static/img/transparent-square.png"

    def test_delegates_to_content_sign_with_default_expiry(self):
        """When `content` is set, the method calls `content.sign(
        expires_in=3600, for_upload=False)` and returns the result
        verbatim. Pin the kwargs so a refactor doesn't accidentally
        flip `for_upload=True` (would produce an upload URL, useless
        for `<img src>`)."""
        calls = []

        class _FakeFileObject:
            def sign(self, *, expires_in, for_upload):
                calls.append({"expires_in": expires_in, "for_upload": for_upload})
                return "https://signed.example/image.jpg"

        class _StandIn:
            content = _FakeFileObject()
            id = "img-1"

        result = BWImage.signed_url(_StandIn())  # type: ignore[arg-type]
        assert result == "https://signed.example/image.jpg"
        assert calls == [{"expires_in": 3600, "for_upload": False}]

    def test_passes_custom_expires_in_through(self):
        """Custom `expires_in` is forwarded as-is. Pin so a future
        refactor doesn't silently clamp / override it."""
        seen = {}

        class _FakeFileObject:
            def sign(self, *, expires_in, for_upload):
                seen["expires_in"] = expires_in
                seen["for_upload"] = for_upload
                return "ok"

        class _StandIn:
            content = _FakeFileObject()
            id = "img-1"

        BWImage.signed_url(_StandIn(), expires_in=60)  # type: ignore[arg-type]
        assert seen == {"expires_in": 60, "for_upload": False}

    def test_runtime_error_from_sign_is_rewrapped(self):
        """If `FileObject.sign` raises `RuntimeError`, the method
        re-raises a `RuntimeError` whose message embeds the image id —
        that's what gives operators a starting point in production
        logs. Pin the chained `__cause__` so the original traceback
        survives."""

        class _Boom:
            def sign(self, *, expires_in, for_upload):
                msg = "backend down"
                raise RuntimeError(msg)

        class _StandIn:
            content = _Boom()
            id = "img-deadbeef"

        with pytest.raises(RuntimeError) as exc_info:
            BWImage.signed_url(_StandIn())  # type: ignore[arg-type]

        msg = str(exc_info.value)
        assert "img-deadbeef" in msg
        assert "backend down" in msg
        assert isinstance(exc_info.value.__cause__, RuntimeError)


class TestPositionalProperties:
    """`is_first` and `is_last` drive the « move up » / « move down »
    buttons in the gallery editor. They are pure functions of
    `position` + the parent's `bw_images` list, so we can pin them
    here without a DB."""

    def test_is_first_when_position_is_zero(self):
        class _StandIn:
            position = 0

        assert BWImage.is_first.fget(_StandIn()) is True  # type: ignore[arg-type]

    def test_is_first_false_when_position_nonzero(self):
        class _StandIn:
            position = 3

        assert BWImage.is_first.fget(_StandIn()) is False  # type: ignore[arg-type]

    def test_is_last_when_position_matches_tail(self):
        """`is_last` is `position == len(parent.bw_images) - 1` — pin
        the off-by-one (must use `- 1`, not `==` against the raw
        length)."""

        class _Parent:
            bw_images: ClassVar[list] = [object(), object(), object()]

        class _StandIn:
            position = 2
            business_wall = _Parent()

        assert BWImage.is_last.fget(_StandIn()) is True  # type: ignore[arg-type]

    def test_is_last_false_when_not_at_tail(self):
        class _Parent:
            bw_images: ClassVar[list] = [object(), object(), object()]

        class _StandIn:
            position = 1
            business_wall = _Parent()

        assert BWImage.is_last.fget(_StandIn()) is False  # type: ignore[arg-type]
