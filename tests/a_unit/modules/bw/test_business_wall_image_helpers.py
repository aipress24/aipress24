# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Unit tests for the BusinessWall <-> BWImage gallery-management
methods at `app.modules.bw.bw_activation.models.business_wall`.

These tests pin the pure list-management logic the gallery editor in
the BW admin UI relies on:

- ``sorted_bw_images`` — returns the children ordered by `position`
  (the editor renders rows in this order).
- ``get_bw_image(image_id)`` — UUID lookup used by the per-image route
  handlers (edit / delete buttons).
- ``add_bw_image(image)`` — appends an image and stamps its position so
  it lands at the tail of the gallery.
- ``delete_bw_image(image)`` — removes an image and *re-numbers* the
  remaining ones so positions stay contiguous (no gaps). This is what
  keeps `is_first` / `is_last` truthful after a delete.
- ``_update_bw_image_positions`` — the private renumberer; tested via
  ``delete_bw_image`` and also directly so accidental rewrites of the
  loop are caught.

A few complementary BWImage properties are also covered here because
they are read by the very same admin templates:
- ``url`` (the public route string),
- ``signed_url(expires_in=...)`` (S3 placeholder fallback + custom
  expiry passthrough),
- ``is_first`` / ``is_last`` (drives the « move up » / « move down »
  buttons in the editor).

We deliberately do NOT touch a database. Real ORM rows are replaced by
duck-typed stand-ins whose attributes match what the methods read
(`.position`, `.id`, `.bw_images`). The methods under test are
intentionally pure with respect to the list attribute, so stand-ins
are the right level of fidelity.

Per project convention we avoid the standard mocking helpers and
avoid captured-call recorders that assert on *interaction*. Where a
collaborator (`FileObject.sign`) is needed, we pass a hand-written
fake that returns a concrete string, and we assert on the returned
*state*, not on whether `sign` was called.
"""

from __future__ import annotations

import inspect as py_inspect
from dataclasses import dataclass, field
from typing import ClassVar
from uuid import UUID, uuid4

import pytest

from app.modules.bw.bw_activation.models.business_wall import BusinessWall, BWImage

# ---------------------------------------------------------------------------
# Stand-ins (duck-typed; no SQLAlchemy session needed)
# ---------------------------------------------------------------------------


@dataclass
class FakeImage:
    """Minimal stand-in for a BWImage row.

    The BusinessWall image-management methods only read `.id` and
    `.position`, so a tiny dataclass is sufficient and far cleaner
    than instantiating a SQLAlchemy mapped row outside a session.
    """

    position: int = 0
    id: UUID = field(default_factory=uuid4)


@dataclass
class FakeBW:
    """Stand-in BusinessWall used to test the image-management methods.

    We bind the production methods to this class via descriptor
    `__get__`, so the methods see a `.bw_images` list attribute just
    like they would on a real `BusinessWall`. This avoids constructing
    a `BusinessWall()` (which has a `bw_images` ClassVar default we
    must not mutate across tests).
    """

    bw_images: list = field(default_factory=list)

    # Bind the real production methods to this fake so they operate on
    # `self.bw_images` and not on the BusinessWall class-level default.
    sorted_bw_images = BusinessWall.sorted_bw_images
    get_bw_image = BusinessWall.get_bw_image
    add_bw_image = BusinessWall.add_bw_image
    delete_bw_image = BusinessWall.delete_bw_image
    _update_bw_image_positions = BusinessWall._update_bw_image_positions


# ---------------------------------------------------------------------------
# sorted_bw_images
# ---------------------------------------------------------------------------


class TestSortedBwImages:
    """The gallery editor renders images by `.position` ascending.
    The property must not depend on insertion order and must not
    mutate the underlying list."""

    def test_empty_gallery_returns_empty_list(self):
        bw = FakeBW(bw_images=[])
        assert bw.sorted_bw_images == []

    def test_single_image_returned_as_is(self):
        img = FakeImage(position=0)
        bw = FakeBW(bw_images=[img])
        assert bw.sorted_bw_images == [img]

    def test_orders_by_position_ascending(self):
        """Out-of-order positions are sorted ascending — that's the
        invariant the editor template iterates on."""
        a = FakeImage(position=2)
        b = FakeImage(position=0)
        c = FakeImage(position=1)
        bw = FakeBW(bw_images=[a, b, c])

        result = bw.sorted_bw_images

        assert [img.position for img in result] == [0, 1, 2]
        assert result == [b, c, a]

    def test_does_not_mutate_underlying_list(self):
        """`sorted_bw_images` returns a NEW list — the underlying
        `bw_images` order MUST stay untouched (or callers who hold a
        reference would see unexpected reorders)."""
        a = FakeImage(position=2)
        b = FakeImage(position=0)
        bw = FakeBW(bw_images=[a, b])

        _ = bw.sorted_bw_images

        # Original list order preserved.
        assert bw.bw_images == [a, b]

    def test_stable_for_equal_positions(self):
        """Python's `sorted` is stable; pin that so a refactor to a
        custom comparator doesn't accidentally shuffle equal-position
        siblings."""
        a = FakeImage(position=0)
        b = FakeImage(position=0)
        c = FakeImage(position=0)
        bw = FakeBW(bw_images=[a, b, c])

        assert bw.sorted_bw_images == [a, b, c]


# ---------------------------------------------------------------------------
# get_bw_image
# ---------------------------------------------------------------------------


class TestGetBwImage:
    """`get_bw_image` is used by the per-image route handlers to look
    up a row by UUID. It must return None (not raise) when the id is
    absent — the handler turns that into a 404."""

    def test_returns_image_when_id_matches(self):
        target = FakeImage()
        other = FakeImage()
        bw = FakeBW(bw_images=[other, target])

        assert bw.get_bw_image(target.id) is target

    def test_returns_none_when_id_not_in_gallery(self):
        bw = FakeBW(bw_images=[FakeImage(), FakeImage()])
        assert bw.get_bw_image(uuid4()) is None

    def test_returns_none_on_empty_gallery(self):
        bw = FakeBW(bw_images=[])
        assert bw.get_bw_image(uuid4()) is None

    def test_returns_first_match_when_ids_collide(self):
        """UUID collisions are vanishingly rare but the implementation
        uses `next(...)` which yields the first match — pin that so a
        refactor to e.g. a dict lookup keeps the same semantics."""
        shared = uuid4()
        first = FakeImage(id=shared)
        second = FakeImage(id=shared)
        bw = FakeBW(bw_images=[first, second])

        assert bw.get_bw_image(shared) is first


# ---------------------------------------------------------------------------
# add_bw_image
# ---------------------------------------------------------------------------


class TestAddBwImage:
    """`add_bw_image` appends an image to the gallery and stamps the
    `position` so the new image lands at the tail. The position
    assignment is the contract — if it stops happening, the editor's
    drag-reorder would see a 0 in the middle of the list."""

    def test_appends_to_empty_gallery_at_position_zero(self):
        bw = FakeBW(bw_images=[])
        img = FakeImage(position=99)  # incoming position is overridden

        bw.add_bw_image(img)

        assert bw.bw_images == [img]
        assert img.position == 0

    def test_position_set_to_tail_of_existing_gallery(self):
        existing = [FakeImage(position=0), FakeImage(position=1)]
        bw = FakeBW(bw_images=list(existing))
        new = FakeImage(position=42)  # incoming position overridden

        bw.add_bw_image(new)

        assert bw.bw_images[-1] is new
        assert new.position == 2

    def test_existing_positions_untouched(self):
        """Adding an image must NOT renumber the existing ones — that
        only happens on delete (`_update_bw_image_positions`)."""
        a = FakeImage(position=0)
        b = FakeImage(position=1)
        bw = FakeBW(bw_images=[a, b])

        bw.add_bw_image(FakeImage())

        assert a.position == 0
        assert b.position == 1

    def test_three_consecutive_adds_produce_contiguous_positions(self):
        """End-to-end check: three adds give positions 0, 1, 2 — pin
        the off-by-one and the « append, then assign » order."""
        bw = FakeBW(bw_images=[])
        a, b, c = FakeImage(), FakeImage(), FakeImage()

        bw.add_bw_image(a)
        bw.add_bw_image(b)
        bw.add_bw_image(c)

        assert [img.position for img in bw.bw_images] == [0, 1, 2]


# ---------------------------------------------------------------------------
# delete_bw_image
# ---------------------------------------------------------------------------


class TestDeleteBwImage:
    """`delete_bw_image` removes an image AND renumbers the remaining
    ones so positions stay contiguous starting at 0. Without the
    renumber, `is_first` / `is_last` would lie and the « move up » /
    « move down » buttons would become incoherent."""

    def test_removes_image_from_list(self):
        a, b = FakeImage(position=0), FakeImage(position=1)
        bw = FakeBW(bw_images=[a, b])

        bw.delete_bw_image(a)

        assert a not in bw.bw_images
        assert bw.bw_images == [b]

    def test_renumbers_survivors_starting_at_zero(self):
        a = FakeImage(position=0)
        b = FakeImage(position=1)
        c = FakeImage(position=2)
        bw = FakeBW(bw_images=[a, b, c])

        bw.delete_bw_image(a)

        # Remaining images renumbered to keep positions contiguous.
        assert b.position == 0
        assert c.position == 1

    def test_deleting_middle_image_renumbers_tail(self):
        """Deleting from the middle must also pull down the indices of
        the tail — otherwise the gallery would have a gap (positions
        0, 2 instead of 0, 1)."""
        a = FakeImage(position=0)
        b = FakeImage(position=1)
        c = FakeImage(position=2)
        bw = FakeBW(bw_images=[a, b, c])

        bw.delete_bw_image(b)

        assert [img.position for img in bw.bw_images] == [0, 1]
        assert a.position == 0
        assert c.position == 1

    def test_deleting_last_image_leaves_others_unchanged(self):
        a = FakeImage(position=0)
        b = FakeImage(position=1)
        bw = FakeBW(bw_images=[a, b])

        bw.delete_bw_image(b)

        assert bw.bw_images == [a]
        assert a.position == 0

    def test_delete_unknown_image_raises_value_error(self):
        """The implementation calls `list.remove` which raises
        ValueError when the element is absent. Pin the exception type
        so the route handler can convert it deterministically."""
        bw = FakeBW(bw_images=[FakeImage(position=0)])
        unknown = FakeImage(position=0)

        with pytest.raises(ValueError):
            bw.delete_bw_image(unknown)


# ---------------------------------------------------------------------------
# _update_bw_image_positions
# ---------------------------------------------------------------------------


class TestUpdateBwImagePositions:
    """The renumberer is private but worth testing in isolation: it
    walks `sorted_bw_images` (already ordered by current position) and
    overwrites positions to a contiguous 0..N-1 range."""

    def test_renumbers_jumbled_positions_to_contiguous_range(self):
        """If positions are 5, 7, 9 (after a series of deletes from a
        bigger gallery), renumbering must collapse them to 0, 1, 2 in
        the same relative order."""
        a = FakeImage(position=5)
        b = FakeImage(position=7)
        c = FakeImage(position=9)
        bw = FakeBW(bw_images=[a, b, c])

        bw._update_bw_image_positions()

        assert [img.position for img in (a, b, c)] == [0, 1, 2]

    def test_preserves_relative_order_by_initial_position(self):
        """Renumbering uses `sorted_bw_images`, so insertion order does
        NOT matter — relative order is dictated by the pre-renumber
        `.position` values."""
        a = FakeImage(position=10)
        b = FakeImage(position=0)
        c = FakeImage(position=5)
        bw = FakeBW(bw_images=[a, b, c])  # insertion order != position order

        bw._update_bw_image_positions()

        # b had the lowest position before → ends at 0; a was highest → ends at 2.
        assert b.position == 0
        assert c.position == 1
        assert a.position == 2

    def test_empty_gallery_is_a_no_op(self):
        bw = FakeBW(bw_images=[])
        bw._update_bw_image_positions()  # must not raise
        assert bw.bw_images == []


# ---------------------------------------------------------------------------
# BWImage.url
# ---------------------------------------------------------------------------


class TestBWImageUrl:
    """`url` is the public route shape `<img src>` reads. Pin the
    literal `/bw/<bw_id>/images/<image_id>` so a refactor of the route
    table is caught at unit-test time."""

    def test_url_uses_business_wall_id_and_image_id(self):
        class _StandIn:
            business_wall_id = "bw-123"
            id = "img-9"

        rendered = BWImage.url.fget(_StandIn())  # type: ignore[arg-type]
        assert rendered == "/bw/bw-123/images/img-9"

    def test_url_does_not_touch_business_wall_relationship(self):
        """The property reads the FK column directly — required so a
        pre-flush row (relationship unloaded) still renders a valid
        URL in the template."""

        class _StandIn:
            business_wall_id = "fk-only"
            id = "img-x"
            business_wall = None  # would crash if `.url` dereferenced this

        rendered = BWImage.url.fget(_StandIn())  # type: ignore[arg-type]
        assert rendered == "/bw/fk-only/images/img-x"


# ---------------------------------------------------------------------------
# BWImage.signed_url
# ---------------------------------------------------------------------------


class _FakeFileObject:
    """Hand-written stand-in for `advanced_alchemy ... FileObject`.

    Returns a deterministic URL embedding the `expires_in` so tests
    can assert on *state* (the rendered URL) rather than on
    interaction (« was sign() called? »). This keeps tests robust to
    refactors that wrap `sign()` in a cache or similar.
    """

    def __init__(self, base: str = "https://signed.example/img") -> None:
        self._base = base

    def sign(self, *, expires_in: int, for_upload: bool) -> str:
        return f"{self._base}?expires_in={expires_in}&for_upload={for_upload}"


class TestSignedUrlExpiry:
    """`signed_url` accepts an optional `expires_in` (default 3600s).
    Test both the default and the custom-value path, plus the
    placeholder fallback when `content is None`."""

    def test_default_expires_in_is_3600(self):
        """Pin the default — some callers omit the kwarg and rely on
        the 1-hour window."""
        sig = py_inspect.signature(BWImage.signed_url)
        assert sig.parameters["expires_in"].default == 3600

    def test_returns_placeholder_when_content_is_none(self):
        class _StandIn:
            content = None
            id = "img-x"

        result = BWImage.signed_url(_StandIn())  # type: ignore[arg-type]
        assert result == "/static/img/transparent-square.png"

    @pytest.mark.parametrize("expires_in", [60, 300, 3600, 7200, 86400])
    def test_custom_expires_in_passes_through_to_sign(self, expires_in):
        """Custom expiry must be forwarded verbatim — no clamping, no
        rounding. We verify state (the URL the stand-in returns
        embeds the value) rather than capturing the call."""

        class _StandIn:
            content = _FakeFileObject()
            id = "img-x"

        result = BWImage.signed_url(  # type: ignore[arg-type]
            _StandIn(), expires_in=expires_in
        )
        assert f"expires_in={expires_in}" in result
        assert "for_upload=False" in result

    def test_for_upload_is_always_false(self):
        """Signing for `<img src>` MUST request a download URL, never
        an upload URL. Pin so a refactor doesn't accidentally flip the
        flag (which would silently break every gallery thumbnail)."""

        class _StandIn:
            content = _FakeFileObject()
            id = "img-x"

        result = BWImage.signed_url(_StandIn())  # type: ignore[arg-type]
        assert "for_upload=False" in result


# ---------------------------------------------------------------------------
# BWImage.is_first / is_last
# ---------------------------------------------------------------------------


class TestPositionalFlags:
    """`is_first` / `is_last` are pure positional checks driving the
    « move up » / « move down » buttons. Their truth value flips
    based on `position` (for is_first) and on the parent's
    `bw_images` length (for is_last)."""

    @pytest.mark.parametrize(
        ("position", "expected"),
        [(0, True), (1, False), (5, False), (-1, False)],
    )
    def test_is_first(self, position, expected):
        class _StandIn:
            pass

        sut = _StandIn()
        sut.position = position
        assert BWImage.is_first.fget(sut) is expected  # type: ignore[arg-type]

    @pytest.mark.parametrize(
        ("position", "n_images", "expected"),
        [
            (0, 1, True),  # single-element gallery — first IS last
            (2, 3, True),  # tail of 3-element gallery
            (1, 3, False),  # middle of 3
            (0, 3, False),  # head of 3 — not last
            (4, 5, True),  # tail of 5-element gallery
        ],
    )
    def test_is_last(self, position, n_images, expected):
        class _Parent:
            bw_images: ClassVar[list] = [object()] * n_images

        class _StandIn:
            pass

        sut = _StandIn()
        sut.position = position
        sut.business_wall = _Parent()
        assert BWImage.is_last.fget(sut) is expected  # type: ignore[arg-type]
