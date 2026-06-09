# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Direct unit coverage for the *pure* helpers that back the
``app.modules.search.adapters`` dispatch surfaces.

The sibling file ``test_adapters_singledispatch.py`` already locks the
end-to-end contracts of ``doc_type`` / ``to_doc`` / ``is_public`` on
each registered model class. This file zooms in one level deeper, on
the small private helpers those overloads compose with:

* ``_to_datetime`` — Arrow → datetime unwrap (wesh's ``DATETIME`` field
  refuses anything that isn't a real ``datetime.datetime``).
* ``_format_tags`` — pure tag-list rendering for the
  ``KEYWORD(commas=True)`` field; missing/empty labels are skipped.
* ``_tags`` — the loader-injected wrapper around ``_format_tags`` (the
  loader defaults to the real DB-backed ``get_tags`` but is overridable
  for tests via Pattern B: default-arg DI).
* ``_is_publicly_visible`` — the shared lifecycle truth-table used by
  Post-like and Event ``is_public`` overloads.
* ``_build_doc`` — the doc-shape skeleton shared by every Post / Event
  / Marketplace ``to_doc``.
* ``doc_id`` — the delete-path shortcut that must agree with the id
  ``to_doc`` would emit.

These helpers are exercised through stand-in plain classes whenever
the helper is dispatch-independent. Where the helper threads through
a ``singledispatch`` registration (``_build_doc`` calls ``doc_type``;
``doc_id`` calls ``doc_type``), we instantiate a real model class so
that the registered overload fires correctly — singledispatch matches
by ``isinstance`` against the registered class, so a stand-in would
fall through to the strict TypeError guard.

The tests verify *outcomes* (returned values, dict keys, primitive
types) rather than internal interactions, in line with the project's
no-mocks rule. Where a collaborator is non-pure (``_tags`` calls a
loader), it is exercised via a real stand-in callable, not a patch.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any, ClassVar

import pytest

from app.models.lifecycle import PublicationStatus
from app.modules.search.adapters import (
    _build_doc,
    _format_tags,
    _is_publicly_visible,
    _tags,
    _to_datetime,
    doc_id,
    doc_type,
)
from app.modules.wire.models import ArticlePost, PressReleasePost
from app.services.tagging import get_tags as real_get_tags

# ---------------------------------------------------------------------
# Stand-ins
# ---------------------------------------------------------------------


class _FakeArrow:
    """Duck-type the bit of ``arrow.Arrow`` that ``_to_datetime``
    cares about: a ``.datetime`` attribute exposing the unwrapped
    ``datetime.datetime``. No other API is required."""

    def __init__(self, inner: datetime) -> None:
        self.datetime = inner


class _LifecycleStub:
    """Minimal stand-in for ``_is_publicly_visible`` — any object that
    exposes the right attributes works (the helper uses ``getattr``).
    Using a plain class keeps the test mock-free."""

    def __init__(
        self,
        *,
        status: PublicationStatus | None = PublicationStatus.PUBLIC,
        published_at: datetime | None = None,
        expires_at: datetime | None = None,
        expired_at: datetime | None = None,
    ) -> None:
        self.status = status
        self.published_at = published_at or datetime(2024, 1, 1, tzinfo=UTC)
        self.expires_at = expires_at
        self.expired_at = expired_at


def _make_real_post(cls, *, pk: int, **kw: Any):
    """Construct a real model instance (no DB) suitable for the
    dispatch-bound helpers (``_build_doc``, ``doc_id``). ``_url`` lets
    ``url_for`` resolve without a Flask app context."""
    obj = cls()
    obj.id = pk
    obj.title = kw.get("title", "T")
    obj.content = kw.get("content", "C")
    obj.summary = kw.get("summary", "S")
    obj.status = kw.get("status", PublicationStatus.PUBLIC)
    obj.published_at = kw.get("published_at", datetime(2024, 1, 1, tzinfo=UTC))
    obj.expires_at = kw.get("expires_at")
    obj._url = kw.get("url", f"/{cls.__name__.lower()}/{pk}")
    return obj


# ---------------------------------------------------------------------
# _to_datetime
# ---------------------------------------------------------------------


class TestToDatetime:
    """``_to_datetime`` exists because wesh's DATETIME field does a
    strict ``isinstance(x, datetime.datetime)`` check and refuses
    Arrow wrappers. We pin both the unwrap and the fall-through
    paths so an Arrow upgrade can't silently regress."""

    def test_none_passes_through(self):
        assert _to_datetime(None) is None

    def test_plain_datetime_is_returned_as_is(self):
        d = datetime(2024, 6, 1, tzinfo=UTC)
        assert _to_datetime(d) is d

    def test_arrow_like_object_is_unwrapped(self):
        inner = datetime(2024, 6, 1, 12, 0, tzinfo=UTC)
        wrapped = _FakeArrow(inner)
        result = _to_datetime(wrapped)
        assert isinstance(result, datetime)
        assert result is inner

    def test_object_without_datetime_attr_is_returned_as_is(self):
        """If we ever feed it a raw timestamp int, the helper just
        passes it through (the caller is expected to validate). Lock
        this contract so behaviour stays predictable."""
        sentinel = "2024-06-01"  # not a datetime, not arrow-like
        assert _to_datetime(sentinel) == sentinel

    def test_datetime_attr_not_a_datetime_falls_back(self):
        """An object that happens to have a ``.datetime`` attribute of
        the wrong type must not get silently unwrapped — we return the
        original object so the caller can decide."""

        class _Decoy:
            datetime = "not-a-datetime"

        decoy = _Decoy()
        assert _to_datetime(decoy) is decoy


# ---------------------------------------------------------------------
# _format_tags / _tags
# ---------------------------------------------------------------------


class TestFormatTags:
    """``_format_tags`` is the pure renderer. The wesh
    ``KEYWORD(commas=True)`` field requires comma-separated string
    tokens, so this rendering is part of the on-disk contract."""

    def test_empty_iterable_yields_empty_string(self):
        assert _format_tags([]) == ""

    def test_joins_labels_with_commas(self):
        apps = [{"label": "foo"}, {"label": "bar"}, {"label": "baz"}]
        assert _format_tags(apps) == "foo,bar,baz"

    def test_drops_entries_without_label_key(self):
        """Tag applications without a label must not produce ``",,foo"``
        style artefacts that would corrupt the KEYWORD tokeniser."""
        apps = [{"label": "foo"}, {"type": "auto"}, {"label": "bar"}]
        assert _format_tags(apps) == "foo,bar"

    def test_drops_entries_with_empty_label(self):
        apps = [{"label": ""}, {"label": "x"}, {"label": None}]
        assert _format_tags(apps) == "x"

    def test_preserves_input_order(self):
        """Callers (the ``get_tags`` service) sort applications before
        handing them off. The renderer must not reorder."""
        apps = [{"label": "zeta"}, {"label": "alpha"}]
        assert _format_tags(apps) == "zeta,alpha"


class TestTags:
    """``_tags`` is the loader-injected wrapper. The default loader is
    the real DB-backed ``get_tags`` (and the try/except is the
    production safety net for the no-session path). Tests inject a
    real callable instead of patching — that's the Pattern B contract."""

    def test_loader_result_is_rendered(self):
        def loader(_obj):
            return [{"label": "a"}, {"label": "b"}]

        assert _tags(object(), loader=loader) == "a,b"

    def test_loader_receives_the_obj_argument(self):
        captured: list[Any] = []

        def loader(obj):
            captured.append(obj)
            return []

        sentinel = object()
        _tags(sentinel, loader=loader)
        assert captured == [sentinel]

    def test_loader_exception_is_swallowed(self):
        """Production safety net: tag lookups happen on event-handler
        paths that may run before the app context is set up. A failing
        loader must NOT propagate — return ``""`` instead."""

        def loader(_obj):
            msg = "no app context"
            raise RuntimeError(msg)

        assert _tags(object(), loader=loader) == ""

    def test_loader_returning_empty_yields_empty_string(self):
        def loader(_obj):
            return []

        assert _tags(object(), loader=loader) == ""

    def test_default_loader_is_get_tags(self):
        """The exported default is the real ``get_tags`` — verify the
        identity so a future rename doesn't silently swap the loader
        and break production tag indexing."""
        assert _tags.__defaults__ is None  # all defaults are kw-only
        # The kw-only loader default lives in __kwdefaults__.
        assert _tags.__kwdefaults__["loader"] is real_get_tags


# ---------------------------------------------------------------------
# _is_publicly_visible
# ---------------------------------------------------------------------


class TestIsPubliclyVisible:
    """The shared lifecycle truth-table used by Post / PressRelease /
    Event ``is_public`` overloads. Tested in isolation here so each
    branch is pinned independently of the singledispatch wiring."""

    def test_public_with_published_at_and_no_expiry(self):
        stub = _LifecycleStub(status=PublicationStatus.PUBLIC)
        assert _is_publicly_visible(stub, expiry_attr="expires_at") is True

    @pytest.mark.parametrize(
        "status",
        [
            PublicationStatus.DRAFT,
            PublicationStatus.ARCHIVED,
            PublicationStatus.EXPIRED,
            None,
        ],
    )
    def test_non_public_status_blocks_indexing(self, status):
        stub = _LifecycleStub(status=status)
        assert _is_publicly_visible(stub, expiry_attr="expires_at") is False

    def test_missing_published_at_blocks_indexing(self):
        stub = _LifecycleStub()
        stub.published_at = None
        assert _is_publicly_visible(stub, expiry_attr="expires_at") is False

    def test_future_expiry_is_indexable(self):
        future = datetime.now(tz=UTC) + timedelta(days=30)
        stub = _LifecycleStub(expires_at=future)
        assert _is_publicly_visible(stub, expiry_attr="expires_at") is True

    def test_past_expiry_blocks_indexing(self):
        past = datetime.now(tz=UTC) - timedelta(days=1)
        stub = _LifecycleStub(expires_at=past)
        assert _is_publicly_visible(stub, expiry_attr="expires_at") is False

    def test_expiry_attr_is_honoured(self):
        """EventPost uses ``expired_at`` (no 's'). The helper reads
        whichever attribute name the caller passes — pin this so the
        Event overload can't drift from the helper."""
        past = datetime.now(tz=UTC) - timedelta(days=1)
        stub = _LifecycleStub(expired_at=past)
        # With expires_at unset but expired_at set, the helper must
        # honour the *passed* attribute name.
        assert _is_publicly_visible(stub, expiry_attr="expired_at") is False
        # Same stub, different attr name → considered no-expiry.
        assert _is_publicly_visible(stub, expiry_attr="expires_at") is True

    def test_arrow_wrapped_published_at_is_accepted(self):
        """The helper threads through ``_to_datetime``, so an Arrow
        wrapper on ``published_at`` must be unwrapped successfully
        rather than treated as "no timestamp"."""
        stub = _LifecycleStub()
        stub.published_at = _FakeArrow(datetime(2024, 6, 1, tzinfo=UTC))
        assert _is_publicly_visible(stub, expiry_attr="expires_at") is True


# ---------------------------------------------------------------------
# _build_doc
# ---------------------------------------------------------------------


class TestBuildDoc:
    """``_build_doc`` defines the canonical doc shape. We exercise it
    via a real ``ArticlePost`` instance so its ``doc_type`` overload
    is dispatched correctly (singledispatch matches by isinstance)."""

    EXPECTED_KEYS: ClassVar[set[str]] = {
        "type",
        "id",
        "title",
        "text",
        "summary",
        "url",
        "timestamp",
        "tags",
    }

    def test_keys_match_canonical_shape(self):
        obj = _make_real_post(ArticlePost, pk=1)
        doc = _build_doc(obj)
        assert set(doc.keys()) == self.EXPECTED_KEYS

    def test_id_is_type_prefixed_primary_key(self):
        obj = _make_real_post(ArticlePost, pk=42)
        doc = _build_doc(obj)
        assert doc["type"] == "article"
        assert doc["id"] == "article:42"

    def test_text_concatenates_title_content_summary(self):
        obj = _make_real_post(
            ArticlePost,
            pk=2,
            title="Hello",
            content="Body",
            summary="Sum",
        )
        assert _build_doc(obj)["text"] == "Hello Body Sum"

    def test_text_drops_empty_segments(self):
        """A space-joined text field must not contain accidental
        double-spaces — they'd leak into the BM25 token stream."""
        obj = _make_real_post(
            ArticlePost,
            pk=3,
            title="OnlyTitle",
            content="",
            summary="",
        )
        assert _build_doc(obj)["text"] == "OnlyTitle"

    def test_falsy_title_becomes_empty_string(self):
        """``title=None`` on the model must not propagate as ``None``
        into the wesh TEXT field — coerce to ``""``."""
        obj = _make_real_post(ArticlePost, pk=4)
        obj.title = None
        assert _build_doc(obj)["title"] == ""

    def test_url_field_is_populated_as_string(self):
        """The ``url_for`` resolver fills the ``url`` slot. We don't
        pin the exact URL (that belongs to the routing test), just
        the contract: a non-None string ends up in the doc."""
        obj = _make_real_post(ArticlePost, pk=5)
        url = _build_doc(obj)["url"]
        assert isinstance(url, str)
        assert url

    def test_timestamp_is_unwrapped_from_arrow(self):
        when = datetime(2024, 6, 1, tzinfo=UTC)
        obj = _make_real_post(ArticlePost, pk=6)
        obj.published_at = _FakeArrow(when)
        assert _build_doc(obj)["timestamp"] is when

    def test_tags_field_is_string(self):
        """No live DB session in this test → ``_tags`` falls through
        its try/except and returns ``""``. The contract is "a string,
        always" so wesh's KEYWORD field never sees ``None``."""
        obj = _make_real_post(ArticlePost, pk=7)
        assert _build_doc(obj)["tags"] == ""

    def test_summary_falls_back_to_description(self):
        """For marketplace rows the model has ``description`` instead
        of ``summary``. ``_build_doc`` must fill the summary slot from
        it. We simulate this on an ArticlePost since the dispatch path
        is identical from ``_build_doc``'s perspective (it just reads
        attributes)."""
        obj = _make_real_post(ArticlePost, pk=8)
        obj.summary = None
        obj.description = "From description"
        doc = _build_doc(obj)
        assert doc["summary"] == "From description"
        assert "From description" in doc["text"]


# ---------------------------------------------------------------------
# doc_id
# ---------------------------------------------------------------------


class TestDocId:
    """``doc_id`` is the cheap delete-path identifier. It MUST agree
    byte-for-byte with the id ``to_doc`` would emit — otherwise a
    delete after an upsert would orphan the document in the index."""

    @pytest.mark.parametrize(
        ("cls", "pk", "expected"),
        [
            (ArticlePost, 1, "article:1"),
            (PressReleasePost, 99, "press_release:99"),
        ],
    )
    def test_composite_id_format(self, cls, pk, expected):
        obj = _make_real_post(cls, pk=pk)
        assert doc_id(obj) == expected

    def test_agrees_with_doc_type(self):
        obj = _make_real_post(ArticlePost, pk=123)
        assert doc_id(obj) == f"{doc_type(obj)}:{obj.id}"

    def test_unknown_type_raises_via_doc_type(self):
        """``doc_id`` defers the type lookup to ``doc_type``, so the
        strict TypeError guard is what we expect for a stray object."""
        with pytest.raises(TypeError, match="No doc_type adapter"):
            doc_id(object())
