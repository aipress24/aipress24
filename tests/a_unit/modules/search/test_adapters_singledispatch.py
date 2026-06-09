# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Pin the contracts of the singledispatch overloads in
``app.modules.search.adapters``.

The adapter module defines three dispatch surfaces — ``doc_type``,
``to_doc`` and ``is_public`` — registered for each indexable source
type (``ArticlePost``, ``PressReleasePost``, ``EventPost``,
``MarketplaceContent`` subclasses, ``User``, ``Organisation``).
These tests:

* lock the canonical type-discriminator strings returned by
  ``doc_type`` — they are part of the on-disk index format and any
  change must be deliberate (it would break existing queries),

* lock the document shape returned by ``to_doc`` — the dict keys and
  JSON-serialisability are a contract with the wesh upsert layer, and

* exercise the public/non-public branches of ``is_public`` so the
  receiver fan-out (upsert vs. delete) stays correct as lifecycle
  rules evolve.

The unknown-type guards on the base ``@singledispatch`` functions are
also covered so we don't silently regress to "anything goes".

We instantiate the real source-type classes (rather than mock objects)
to exercise the actual MRO walk that ``singledispatch`` performs;
``_url`` is set on each instance so ``app.flask.routing.url_for`` can
resolve without a live Flask app context.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.models.auth import User
from app.models.lifecycle import PublicationStatus
from app.models.organisation import Organisation
from app.modules.biz.models import JobOffer, MissionOffer, ProjectOffer
from app.modules.events.models import EventPost
from app.modules.search.adapters import (
    doc_id,
    doc_type,
    is_public,
    to_doc,
)
from app.modules.wire.models import ArticlePost, PressReleasePost

# ---------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------

EXPECTED_DOC_KEYS = {
    "type",
    "id",
    "title",
    "text",
    "summary",
    "url",
    "timestamp",
    "tags",
}


def _make_post(
    cls,
    *,
    pk: int,
    title: str = "T",
    content: str = "C",
    summary: str = "S",
    status: PublicationStatus = PublicationStatus.PUBLIC,
    published_at: datetime | None = None,
    expires_at: datetime | None = None,
):
    """Build an in-memory ArticlePost / PressReleasePost / EventPost.

    We bypass the DB by setting attributes directly; the adapter never
    touches the session — it only reads attributes.
    """
    obj = cls()
    obj.id = pk
    obj.title = title
    obj.content = content
    obj.summary = summary
    obj.status = status
    obj.published_at = published_at or datetime(2024, 1, 1, tzinfo=UTC)
    # EventPost uses ``expired_at`` (note the d), Article/PressRelease
    # use ``expires_at``. We set the matching attribute for the type.
    if cls is EventPost:
        obj.expired_at = expires_at
    else:
        obj.expires_at = expires_at
    obj._url = f"/{cls.__name__.lower()}/{pk}"
    return obj


# ---------------------------------------------------------------------
# doc_type — type discriminator strings
# ---------------------------------------------------------------------


class TestDocType:
    """The discriminator string is the on-disk type tag, baked into
    every document id (``"<type>:<pk>"``) and used for delete-by-type.
    Changes here are breaking changes for any existing index."""

    @pytest.mark.parametrize(
        ("cls", "expected"),
        [
            (ArticlePost, "article"),
            (PressReleasePost, "press_release"),
            (EventPost, "event"),
        ],
    )
    def test_post_like_types(self, cls, expected):
        obj = _make_post(cls, pk=1)
        assert doc_type(obj) == expected

    @pytest.mark.parametrize(
        ("cls", "expected"),
        [
            (MissionOffer, "mission_offer"),
            (ProjectOffer, "project_offer"),
            (JobOffer, "job_offer"),
        ],
    )
    def test_marketplace_uses_polymorphic_identity(self, cls, expected):
        # The marketplace adapter reads ``obj.type`` (the polymorphic
        # identity). We verify the polymorphic identity hasn't drifted
        # from what the index expects.
        obj = cls()
        assert doc_type(obj) == expected

    def test_user(self):
        assert doc_type(User()) == "user"

    def test_organisation(self):
        assert doc_type(Organisation(name="x")) == "organisation"

    def test_unknown_type_raises(self):
        """The base singledispatch is a strict guard: a stray object
        must not silently become an indexable document."""
        with pytest.raises(TypeError, match="No doc_type adapter"):
            doc_type(object())


# ---------------------------------------------------------------------
# to_doc — document shape
# ---------------------------------------------------------------------


class TestToDoc:
    """Pin the document shape: keys present, primitive-typed values
    that wesh / SQLAlchemyStorage can serialise."""

    @pytest.mark.parametrize(
        "cls",
        [ArticlePost, PressReleasePost, EventPost],
    )
    def test_shape_is_canonical(self, cls):
        obj = _make_post(cls, pk=10, title="Hello", content="Body", summary="Sum")
        doc = to_doc(obj)
        assert set(doc.keys()) == EXPECTED_DOC_KEYS
        # type / id agree with doc_type / doc_id
        assert doc["type"] == doc_type(obj)
        assert doc["id"] == f"{doc_type(obj)}:10"
        # text concatenates title + content + summary (drops empties)
        assert "Hello" in doc["text"]
        assert "Body" in doc["text"]
        assert "Sum" in doc["text"]

    def test_text_drops_empty_segments(self):
        """The ``text`` field is space-joined with empty parts filtered.
        Verifying this prevents accidental double-spaces leaking into
        the BM25 token stream."""
        obj = _make_post(ArticlePost, pk=11, title="A", content="", summary="")
        assert to_doc(obj)["text"] == "A"

    def test_timestamp_is_datetime_not_arrow(self):
        """wesh's DATETIME field checks ``isinstance(x, datetime)`` —
        Arrow wrappers must be unwrapped before reaching ``upsert``."""
        published = datetime(2024, 6, 1, tzinfo=UTC)
        obj = _make_post(ArticlePost, pk=12, published_at=published)
        assert to_doc(obj)["timestamp"] == published
        assert isinstance(to_doc(obj)["timestamp"], datetime)

    def test_values_are_json_serialisable_primitives(self):
        """The doc should contain only str / int / list / datetime —
        i.e. types that the SQL/Ram backends understand without help."""
        obj = _make_post(EventPost, pk=13)
        doc = to_doc(obj)
        ok_types = (str, int, type(None), datetime, list)
        for key, value in doc.items():
            assert isinstance(value, ok_types), f"{key} is {type(value).__name__}"

    def test_marketplace_uses_description_when_summary_absent(self):
        """Marketplace rows have ``description`` instead of ``summary``.
        ``_build_doc`` falls back to ``description`` so the summary slot
        still gets filled."""
        m = MissionOffer()
        m.id = 14
        m.title = "Title"
        m.description = "Mission description"
        m._url = "/m/14"
        doc = to_doc(m)
        assert doc["summary"] == "Mission description"
        assert "Mission description" in doc["text"]

    def test_user_doc_shape(self):
        u = User()
        u.id = 21
        u.first_name = "Jane"
        u.last_name = "Doe"
        u.email = "jane@example.com"
        u._url = "/u/21"
        doc = to_doc(u)
        assert doc["type"] == "user"
        assert doc["id"] == "user:21"
        assert doc["title"] == "Jane Doe"
        assert "Jane" in doc["text"] and "Doe" in doc["text"]
        assert doc["tags"] == ""

    def test_user_title_falls_back_to_email_when_name_empty(self):
        """Defensive branch: an account validated before name capture
        should still produce a non-empty index title (else search hits
        render as a blank link)."""
        u = User()
        u.id = 22
        u.first_name = ""
        u.last_name = ""
        u.email = "anon@example.com"
        u._url = "/u/22"
        assert to_doc(u)["title"] == "anon@example.com"

    def test_organisation_doc_shape(self):
        o = Organisation(name="Acme")
        o.id = 31
        o.bw_name = "Acme BW"
        o._url = "/o/31"
        doc = to_doc(o)
        assert doc["type"] == "organisation"
        assert doc["title"] == "Acme"
        assert "Acme BW" in doc["text"]

    def test_unknown_type_raises(self):
        with pytest.raises(TypeError, match="No to_doc adapter"):
            to_doc(object())

    def test_doc_id_matches_to_doc_id(self):
        """``doc_id`` is the delete-path shortcut and MUST agree with
        the id ``to_doc`` would produce — else a delete after an
        upsert would orphan the original document."""
        obj = _make_post(PressReleasePost, pk=99)
        assert doc_id(obj) == to_doc(obj)["id"] == "press_release:99"


# ---------------------------------------------------------------------
# is_public — indexability gate
# ---------------------------------------------------------------------


class TestIsPublic:
    """The receiver upserts when ``is_public`` is True and deletes
    otherwise. These tests pin the lifecycle truth-table per type."""

    @pytest.mark.parametrize(
        "cls",
        [ArticlePost, PressReleasePost, EventPost],
    )
    def test_public_with_published_at_is_indexable(self, cls):
        obj = _make_post(cls, pk=1, status=PublicationStatus.PUBLIC)
        assert is_public(obj) is True

    @pytest.mark.parametrize(
        ("cls", "status"),
        [
            (ArticlePost, PublicationStatus.DRAFT),
            (ArticlePost, PublicationStatus.ARCHIVED),
            (PressReleasePost, PublicationStatus.DRAFT),
            (PressReleasePost, PublicationStatus.EXPIRED),
            (EventPost, PublicationStatus.DRAFT),
        ],
    )
    def test_non_public_status_is_not_indexable(self, cls, status):
        obj = _make_post(cls, pk=2, status=status)
        assert is_public(obj) is False

    @pytest.mark.parametrize(
        "cls",
        [ArticlePost, PressReleasePost, EventPost],
    )
    def test_missing_published_at_blocks_indexing(self, cls):
        """A row promoted to PUBLIC but without a timestamp is in an
        inconsistent state — keep it out of the index until the
        lifecycle hook backfills ``published_at``."""
        obj = _make_post(cls, pk=3, status=PublicationStatus.PUBLIC)
        obj.published_at = None
        assert is_public(obj) is False

    def test_expired_article_is_not_indexable(self):
        past = datetime.now(tz=UTC) - timedelta(days=1)
        obj = _make_post(ArticlePost, pk=4, expires_at=past)
        assert is_public(obj) is False

    def test_future_expiry_article_is_indexable(self):
        future = datetime.now(tz=UTC) + timedelta(days=30)
        obj = _make_post(ArticlePost, pk=5, expires_at=future)
        assert is_public(obj) is True

    def test_event_uses_expired_at_attribute(self):
        """EventPost reads ``expired_at`` (no 's') — distinct from
        the Post lifecycle ``expires_at``. Regression guard against
        accidental rename."""
        past = datetime.now(tz=UTC) - timedelta(days=1)
        obj = _make_post(EventPost, pk=6, expires_at=past)
        # expired_at in the past → not indexable
        assert is_public(obj) is False

    @pytest.mark.parametrize(
        ("cls", "expected"),
        [
            (MissionOffer, True),
            (ProjectOffer, True),
            (JobOffer, True),
        ],
    )
    def test_marketplace_public_status_only(self, cls, expected):
        """Marketplace lifecycle skips ``published_at`` — status alone
        decides visibility."""
        m = cls()
        m.status = PublicationStatus.PUBLIC
        assert is_public(m) is expected

    @pytest.mark.parametrize(
        "status",
        [
            PublicationStatus.DRAFT,
            PublicationStatus.ARCHIVED,
            PublicationStatus.EXPIRED,
        ],
    )
    def test_marketplace_non_public_is_not_indexable(self, status):
        m = MissionOffer()
        m.status = status
        assert is_public(m) is False

    def test_user_active_and_validated_is_indexable(self):
        u = User()
        u.active = True
        u.validated_at = datetime(2024, 1, 1, tzinfo=UTC)
        u.deleted_at = None
        assert is_public(u) is True

    @pytest.mark.parametrize(
        ("active", "validated_at", "deleted_at"),
        [
            (False, datetime(2024, 1, 1, tzinfo=UTC), None),  # inactive
            (True, None, None),  # never validated
            (True, datetime(2024, 1, 1, tzinfo=UTC), datetime(2024, 6, 1, tzinfo=UTC)),
        ],
    )
    def test_user_negative_cases(self, active, validated_at, deleted_at):
        u = User()
        u.active = active
        u.validated_at = validated_at
        u.deleted_at = deleted_at
        assert is_public(u) is False

    def test_organisation_active_and_not_deleted_is_indexable(self):
        o = Organisation(name="Acme")
        o.active = True
        o.deleted_at = None
        assert is_public(o) is True

    @pytest.mark.parametrize(
        ("active", "deleted_at"),
        [
            (False, None),
            (True, datetime(2024, 6, 1, tzinfo=UTC)),
        ],
    )
    def test_organisation_negative_cases(self, active, deleted_at):
        o = Organisation(name="Acme")
        o.active = active
        o.deleted_at = deleted_at
        assert is_public(o) is False

    def test_unknown_type_raises(self):
        with pytest.raises(TypeError, match="No is_public adapter"):
            is_public(object())
