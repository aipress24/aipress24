# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Unit tests pinning the *shape* and the *pure business logic* of the
`Event` (and adjacent `EventImage`) SQLAlchemy mapped classes at
`app.modules.wip.models.eventroom.event`.

WHY these tests exist :

- The `Event` model is the spine of the public /events/ list. Its
  column inventory, default values, FK targets and status enum are
  read by view code, search indexers, templates and Alembic migrations.
  Renaming a column or flipping a default silently breaks all of them.
- The `publish()` / `unpublish()` / `set_schedule()` helpers contain the
  *business rules* (bug #0172 in particular: an event without dates is
  invisible on the public list, so the publish flow must refuse to
  publish it). These rules must be pinned so a refactor does not
  re-introduce the silent-invisibility bug.
- The `is_draft` / `is_public` / `is_expired` properties are read by
  templates — `is_expired` in particular has to be timezone-safe
  because legacy rows may carry naive datetimes.
- The image-management helpers (`add_image`, `delete_image`,
  `update_image_positions`, `sorted_images`, `get_image`) are pure
  Python operating on the in-memory `images` list — perfect candidates
  for a_unit coverage.

These tests do NOT touch a database. We introspect SQLAlchemy metadata
for shape, and invoke unbound methods against duck-typed stand-in
objects for behaviour. DB-bound concerns (cascade firing on a real
DELETE, INSERT defaults running) belong in `b_integration`.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import ClassVar

import arrow
import pytest
import sqlalchemy as sa

from app.models.lifecycle import PublicationStatus
from app.modules.wip.models.eventroom.event import DRAFT, Event, EventImage


def _column(model, name):
    """Fetch a column from a mapped class without instantiating a row."""
    return model.__table__.columns[name]


# ---------------------------------------------------------------------------
# Shape
# ---------------------------------------------------------------------------


class TestEventClassShape:
    """The class must be a SQLAlchemy mapped class with a stable
    `__tablename__`. The tablename is referenced by Alembic migrations
    and by any raw SQL in dashboard widgets — renaming it without a
    migration would silently break SELECTs."""

    def test_tablename(self):
        assert Event.__tablename__ == "evr_event"

    def test_event_image_tablename(self):
        assert EventImage.__tablename__ == "evr_image"

    def test_module_level_draft_alias(self):
        """`DRAFT` is re-exported at module level and used as the default
        for the `status` column. Pin it to catch an accidental rename."""
        assert DRAFT is PublicationStatus.DRAFT


class TestEventColumns:
    """The column set is the table's contract with the rest of the
    codebase : view code, search, templates and migrations all read
    these names. Pin the inventory so a typo-rename surfaces here."""

    EXPECTED_COLUMNS: ClassVar[set[str]] = {
        # From IdMixin
        "id",
        # From LifeCycleMixin
        "created_at",
        "modified_at",
        "deleted_at",
        # From Owned
        "owner_id",
        # Content
        "chapo",
        "contenu",
        "titre",
        # Status & publication dates
        "status",
        "published_at",
        "expired_at",
        # Schedule
        "start_time",
        "end_time",
        # Publisher org
        "publisher_id",
        # Classification
        "event_type",
        "sector",
        # Localisation
        "address",
        "pays_zip_ville",
        "pays_zip_ville_detail",
        "url",
        # Language
        "language",
    }

    def test_expected_columns_all_present(self):
        actual = set(Event.__table__.columns.keys())
        missing = self.EXPECTED_COLUMNS - actual
        assert not missing, f"Missing columns on Event: {missing}"

    @pytest.mark.parametrize(
        "col_name",
        [
            "chapo",
            "contenu",
            "titre",
            "event_type",
            "sector",
            "address",
            "pays_zip_ville",
            "pays_zip_ville_detail",
            "url",
        ],
    )
    def test_text_columns_default_to_empty_string(self, col_name):
        """All free-form text columns default to `""` (not NULL) so
        downstream `.strip()` / template rendering is safe."""
        col = _column(Event, col_name)
        assert col.default is not None
        assert col.default.arg == ""

    def test_language_default_is_french(self):
        """The product is FR-first ; `language` defaulting to "fr" is
        a deliberate choice that templates and search indexers depend
        on. A switch to "" or "en" would change indexing behaviour."""
        col = _column(Event, "language")
        assert col.default.arg == "fr"

    @pytest.mark.parametrize(
        "col_name",
        ["published_at", "expired_at", "start_time", "end_time"],
    )
    def test_datetime_columns_are_nullable(self, col_name):
        """A freshly-created (draft) event has no schedule and no
        publication dates yet — these MUST be nullable, otherwise
        creating a draft would fail at INSERT."""
        assert _column(Event, col_name).nullable is True

    def test_publisher_id_fk_target(self):
        """`publisher_id` must point at `crp_organisation.id` so the
        org-side queries (« events published by this BW ») can join."""
        col = _column(Event, "publisher_id")
        fks = list(col.foreign_keys)
        assert len(fks) == 1
        assert fks[0].column.table.name == "crp_organisation"
        assert fks[0].column.name == "id"


class TestStatusColumn:
    """The `status` column is the lynchpin of the publication workflow.
    Its default MUST be `DRAFT` — if a refactor swaps the default to
    `PUBLIC`, every newly-created event would land on the public list
    without the author's intent."""

    def test_status_type_is_enum(self):
        col = _column(Event, "status")
        assert isinstance(col.type, sa.Enum)

    def test_status_default_is_draft(self):
        col = _column(Event, "status")
        assert col.default is not None
        # The default is the enum member itself (not the string value)
        assert col.default.arg is PublicationStatus.DRAFT


class TestEventImageShape:
    """`EventImage` carries the carousel images of an event. Its FK to
    `evr_event` must be NOT NULL and ON DELETE CASCADE — deleting an
    event must clean up its images, otherwise orphan S3 references
    accumulate."""

    def test_event_id_not_nullable(self):
        assert _column(EventImage, "event_id").nullable is False

    def test_event_id_fk_target_and_cascade(self):
        col = _column(EventImage, "event_id")
        fks = list(col.foreign_keys)
        assert len(fks) == 1
        assert fks[0].column.table.name == "evr_event"
        assert fks[0].column.name == "id"
        assert fks[0].ondelete == "CASCADE"

    def test_position_default_is_zero(self):
        """A freshly-added image with no explicit position must land
        at 0 so it shows up first in an empty carousel."""
        col = _column(EventImage, "position")
        assert col.default is not None
        assert col.default.arg == 0


# ---------------------------------------------------------------------------
# Pure helpers / properties
# ---------------------------------------------------------------------------


class _EventStub:
    """Duck-typed stand-in for an `Event` instance. We re-bind the
    methods (and the `sorted_images` property) we need so the unbound
    `Event.<method>(stub)` calls below can resolve `self.can_publish`,
    `self.update_image_positions`, `self.sorted_images`, etc."""

    can_publish = Event.can_publish
    can_unpublish = Event.can_unpublish
    update_image_positions = Event.update_image_positions
    sorted_images = Event.sorted_images

    def __init__(self, **kwargs):
        # Sensible defaults for a happy-path draft event
        self.status = PublicationStatus.DRAFT
        self.titre = "My Event"
        self.contenu = "Some content"
        self.start_time = datetime(2026, 1, 1, tzinfo=UTC)
        self.end_time = datetime(2026, 1, 2, tzinfo=UTC)
        self.published_at = None
        self.publisher_id = None
        self.expired_at = None
        self.images = []
        for key, val in kwargs.items():
            setattr(self, key, val)


class TestTitleAlias:
    """`title` is a thin alias for `titre`. It exists for templates that
    were written in English while the column kept its French name. Pin
    the alias so a refactor doesn't break those templates."""

    def test_title_returns_titre(self):
        stub = _EventStub(titre="Hello")
        assert Event.title.fget(stub) == "Hello"


class TestStatusProperties:
    """`is_draft` and `is_public` drive every template branch for
    « show edit button » / « show on public list ». Pinning them
    protects template logic from a status-rename refactor."""

    @pytest.mark.parametrize(
        ("status", "expected_draft", "expected_public"),
        [
            (PublicationStatus.DRAFT, True, False),
            (PublicationStatus.PUBLIC, False, True),
            (PublicationStatus.ARCHIVED, False, False),
            (PublicationStatus.EXPIRED, False, False),
        ],
    )
    def test_status_property_matrix(self, status, expected_draft, expected_public):
        stub = _EventStub(status=status)
        assert Event.is_draft.fget(stub) is expected_draft
        assert Event.is_public.fget(stub) is expected_public


class TestIsExpired:
    """`is_expired` must be timezone-safe : legacy rows may carry a
    naive datetime in `expired_at`. Comparing a naive datetime against
    `datetime.now(UTC)` raises in Python — the property has explicit
    fallback code that this test pins."""

    def test_is_expired_is_false_when_expired_at_is_none(self):
        stub = _EventStub(expired_at=None)
        assert Event.is_expired.fget(stub) is False

    def test_is_expired_true_for_aware_past_date(self):
        past = datetime(2000, 1, 1, tzinfo=UTC)
        stub = _EventStub(expired_at=past)
        assert Event.is_expired.fget(stub) is True

    def test_is_expired_false_for_aware_future_date(self):
        future = datetime(2999, 1, 1, tzinfo=UTC)
        stub = _EventStub(expired_at=future)
        assert Event.is_expired.fget(stub) is False

    def test_is_expired_handles_naive_datetime(self):
        """Legacy rows may carry a naive datetime ; comparing to
        `datetime.now(UTC)` would raise without the fallback. Pin the
        behaviour : naive past = expired, no crash."""
        naive_past = datetime(2000, 1, 1)  # noqa: DTZ001
        stub = _EventStub(expired_at=naive_past)
        assert Event.is_expired.fget(stub) is True


# ---------------------------------------------------------------------------
# set_schedule
# ---------------------------------------------------------------------------


class TestSetSchedule:
    """`set_schedule` is the « set the dates » helper. It must :
    (a) refuse end-before-start (silent inversion would corrupt the
        public-list date filter) ;
    (b) normalise naive datetimes to UTC so downstream comparisons
        never crash on tz-mismatch."""

    def test_happy_path_aware_datetimes(self):
        stub = _EventStub()
        start = datetime(2026, 6, 1, 10, tzinfo=UTC)
        end = datetime(2026, 6, 1, 12, tzinfo=UTC)
        Event.set_schedule(stub, start, end)
        assert stub.start_time == start
        assert stub.end_time == end

    def test_naive_datetimes_are_normalised_to_utc(self):
        stub = _EventStub()
        naive_start = datetime(2026, 6, 1, 10)  # noqa: DTZ001
        naive_end = datetime(2026, 6, 1, 12)  # noqa: DTZ001
        Event.set_schedule(stub, naive_start, naive_end)
        assert stub.start_time.tzinfo is UTC
        assert stub.end_time.tzinfo is UTC

    def test_end_before_start_raises(self):
        stub = _EventStub()
        start = datetime(2026, 6, 1, 12, tzinfo=UTC)
        end = datetime(2026, 6, 1, 10, tzinfo=UTC)
        with pytest.raises(ValueError, match="end_time must be after start_time"):
            Event.set_schedule(stub, start, end)

    def test_equal_start_and_end_is_allowed(self):
        """A zero-duration event (e.g. a marker timestamp) is not
        explicitly forbidden — pin so a future « strictly greater »
        check is a deliberate decision."""
        stub = _EventStub()
        same = datetime(2026, 6, 1, 12, tzinfo=UTC)
        Event.set_schedule(stub, same, same)
        assert stub.start_time == stub.end_time == same


# ---------------------------------------------------------------------------
# publish / unpublish workflow
# ---------------------------------------------------------------------------


class TestCanPublish:
    """`can_publish` gates `publish()`. Only DRAFT events may be
    published — re-publishing a PUBLIC event would clobber the original
    `published_at` if `publish()` were called blindly."""

    @pytest.mark.parametrize(
        ("status", "expected"),
        [
            (PublicationStatus.DRAFT, True),
            (PublicationStatus.PUBLIC, False),
            (PublicationStatus.ARCHIVED, False),
            (PublicationStatus.EXPIRED, False),
        ],
    )
    def test_can_publish_only_from_draft(self, status, expected):
        stub = _EventStub(status=status)
        assert Event.can_publish(stub) is expected


class TestCanUnpublish:
    """`can_unpublish` is the symmetric guard. Only PUBLIC events may
    be returned to DRAFT — unpublishing a DRAFT is a no-op that should
    surface as an error so the caller knows their UI is out of sync."""

    @pytest.mark.parametrize(
        ("status", "expected"),
        [
            (PublicationStatus.PUBLIC, True),
            (PublicationStatus.DRAFT, False),
            (PublicationStatus.ARCHIVED, False),
        ],
    )
    def test_can_unpublish_only_from_public(self, status, expected):
        stub = _EventStub(status=status)
        assert Event.can_unpublish(stub) is expected


class TestPublish:
    """`publish()` is the most-rule-heavy method on `Event`. Each
    branch corresponds to a real bug or product rule — bug #0172 in
    particular requires both dates to be set BEFORE publish, otherwise
    the event is invisible on the public list."""

    def test_publish_happy_path_sets_status_and_published_at(self):
        stub = _EventStub()
        Event.publish(stub)
        assert stub.status == PublicationStatus.PUBLIC
        assert stub.published_at is not None
        # `arrow.now(...)` is used internally
        assert isinstance(stub.published_at, arrow.Arrow)

    def test_publish_preserves_existing_published_at(self):
        """Re-publishing (after unpublish + edit + publish again) must
        not overwrite the original `published_at` — it is the canonical
        « first published » timestamp displayed to users."""
        first = arrow.get("2025-01-01T00:00:00+00:00")
        stub = _EventStub(published_at=first)
        Event.publish(stub)
        assert stub.published_at == first

    def test_publish_sets_publisher_id_when_provided(self):
        stub = _EventStub()
        Event.publish(stub, publisher_id=42)
        assert stub.publisher_id == 42

    def test_publish_leaves_publisher_id_alone_when_not_provided(self):
        stub = _EventStub(publisher_id=7)
        Event.publish(stub)
        assert stub.publisher_id == 7

    def test_publish_fails_if_not_draft(self):
        stub = _EventStub(status=PublicationStatus.PUBLIC)
        with pytest.raises(ValueError, match="not in DRAFT status"):
            Event.publish(stub)

    @pytest.mark.parametrize("titre", ["", "   "])
    def test_publish_fails_on_empty_titre(self, titre):
        """Whitespace-only titles must be rejected — they would render
        as an empty card on the public list."""
        stub = _EventStub(titre=titre)
        with pytest.raises(ValueError, match="titre is required"):
            Event.publish(stub)

    @pytest.mark.parametrize("contenu", ["", "   "])
    def test_publish_fails_on_empty_contenu(self, contenu):
        stub = _EventStub(contenu=contenu)
        with pytest.raises(ValueError, match="contenu is required"):
            Event.publish(stub)

    @pytest.mark.parametrize("missing_field", ["start_time", "end_time"])
    def test_publish_fails_without_dates_bug_0172(self, missing_field):
        """Bug #0172 : an event without start_time OR without end_time
        would be silently filtered out of the public list. Publish
        must refuse with an explicit (French) error message."""
        stub = _EventStub(**{missing_field: None})
        with pytest.raises(ValueError, match="date de début"):
            Event.publish(stub)

    def test_publish_fails_when_end_before_start(self):
        stub = _EventStub(
            start_time=datetime(2026, 6, 1, 12, tzinfo=UTC),
            end_time=datetime(2026, 6, 1, 10, tzinfo=UTC),
        )
        with pytest.raises(ValueError, match="end_time must be after start_time"):
            Event.publish(stub)

    def test_publish_tolerates_naive_datetimes_on_event(self):
        """If a legacy row carries naive `start_time` / `end_time`,
        publish must still work — the method normalises to UTC for
        the comparison."""
        stub = _EventStub(
            start_time=datetime(2026, 6, 1, 10),  # noqa: DTZ001
            end_time=datetime(2026, 6, 1, 12),  # noqa: DTZ001
        )
        Event.publish(stub)
        assert stub.status == PublicationStatus.PUBLIC


class TestUnpublish:
    """`unpublish()` returns a published event to DRAFT so the author
    can edit it. It must refuse to unpublish a non-PUBLIC event (the
    UI may be out of sync) and it must NOT clear `published_at` —
    that timestamp is the canonical « first published » marker."""

    def test_unpublish_resets_status_to_draft(self):
        stub = _EventStub(status=PublicationStatus.PUBLIC)
        Event.unpublish(stub)
        assert stub.status == PublicationStatus.DRAFT

    def test_unpublish_fails_if_not_public(self):
        stub = _EventStub(status=PublicationStatus.DRAFT)
        with pytest.raises(ValueError, match="not PUBLIC"):
            Event.unpublish(stub)

    def test_unpublish_does_not_clear_published_at(self):
        original = arrow.get("2025-01-01T00:00:00+00:00")
        stub = _EventStub(
            status=PublicationStatus.PUBLIC,
            published_at=original,
        )
        Event.unpublish(stub)
        assert stub.published_at == original


# ---------------------------------------------------------------------------
# Image management helpers
# ---------------------------------------------------------------------------


class _ImageStub:
    """Duck-typed stand-in for an `EventImage`."""

    def __init__(self, image_id: int = 0, position: int = 0):
        self.id = image_id
        self.position = position


class TestImageHelpers:
    """The image-management helpers operate on the in-memory `images`
    list — pure Python, no DB. They are responsible for keeping
    `position` contiguous and zero-based so the carousel renders in
    the expected order."""

    def test_sorted_images_returns_images_by_position(self):
        stub = _EventStub(
            images=[
                _ImageStub(image_id=3, position=3),
                _ImageStub(image_id=1, position=1),
                _ImageStub(image_id=2, position=2),
                _ImageStub(image_id=0, position=0),
            ]
        )
        result = Event.sorted_images.fget(stub)
        assert [img.position for img in result] == [0, 1, 2, 3]

    def test_sorted_images_returns_new_list(self):
        """`sorted_images` MUST NOT mutate `self.images` in place
        (templates and add/delete logic depend on stable insertion
        order until `update_image_positions` is called)."""
        originals = [_ImageStub(position=2), _ImageStub(position=1)]
        stub = _EventStub(images=originals)
        Event.sorted_images.fget(stub)
        assert [img.position for img in stub.images] == [2, 1]

    def test_get_image_finds_by_id(self):
        stub = _EventStub(
            images=[
                _ImageStub(image_id=1),
                _ImageStub(image_id=2),
                _ImageStub(image_id=3),
            ]
        )
        found = Event.get_image(stub, 2)
        assert found is not None
        assert found.id == 2

    def test_get_image_returns_none_when_missing(self):
        stub = _EventStub(images=[_ImageStub(image_id=1)])
        assert Event.get_image(stub, 999) is None

    def test_add_image_appends_and_sets_position(self):
        stub = _EventStub(images=[])
        first = _ImageStub(image_id=1)
        Event.add_image(stub, first)
        assert stub.images == [first]
        assert first.position == 0

        second = _ImageStub(image_id=2)
        Event.add_image(stub, second)
        assert stub.images == [first, second]
        assert second.position == 1

    def test_delete_image_reindexes_remaining_positions(self):
        """After deleting the middle image, the remaining positions
        must be contiguous (0..N-1) so the carousel does not display
        a gap."""
        images = [
            _ImageStub(image_id=1, position=0),
            _ImageStub(image_id=2, position=1),
            _ImageStub(image_id=3, position=2),
        ]
        stub = _EventStub(images=images)
        Event.delete_image(stub, images[1])
        assert [img.id for img in stub.images] == [1, 3]
        assert [img.position for img in stub.images] == [0, 1]

    def test_update_image_positions_normalises_to_contiguous_range(self):
        """Pin the post-condition : after `update_image_positions`,
        every image has a position equal to its sort-order index."""
        images = [
            _ImageStub(image_id=1, position=7),
            _ImageStub(image_id=2, position=42),
            _ImageStub(image_id=3, position=99),
        ]
        stub = _EventStub(images=images)
        Event.update_image_positions(stub)
        assert sorted(img.position for img in images) == [0, 1, 2]
