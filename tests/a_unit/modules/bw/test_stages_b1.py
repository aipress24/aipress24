# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Unit tests for stage B1 / B1b pure helpers (paid BW tier activation).

Stages B1 and B1b sit at the heart of the paid Business Wall onboarding
flow (BW4T, BW4L&E, BW4PR). The Flask routes mix DB writes, S3 uploads,
session bookkeeping and Stripe-portal redirects — which makes them hard
to exercise as a whole.

The strategy here follows Pattern A from the testing pyramid plan: we
keep the imperative Flask shells thin and extract the *decision* logic
into pure functions (``content_form_missing_required``,
``gallery_upload_outcome``, ``gallery_swap_positions``). These tests
exercise those decisions with plain dicts and stand-in objects — no
Flask, no DB, no test doubles, no fixture patching.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest

from app.modules.bw.bw_activation.routes.stage_b1 import (
    content_form_missing_required,
)
from app.modules.bw.bw_activation.routes.stage_b1b import (
    gallery_swap_positions,
    gallery_upload_outcome,
)

# --- Stand-in objects (Pattern C: real-fake collaborator) -----------------


@dataclass
class FakeGalleryImage:
    """Stand-in for `BWImage` used by gallery-swap tests."""

    id: int
    position: int = 0


# --- content_form_missing_required ----------------------------------------


class TestContentFormMissingRequired:
    """``name`` and ``siren`` are the only hard-required fields."""

    def test_no_missing_when_both_present(self):
        assert (
            content_form_missing_required({"name": "ACME", "siren": "123456789"}) == []
        )

    def test_both_missing_when_empty(self):
        assert content_form_missing_required({}) == ["name", "siren"]

    @pytest.mark.parametrize(
        ("form", "expected"),
        [
            (
                {"name": "  ", "siren": "12345"},
                ["name"],
            ),  # whitespace-only counts as missing
            ({"name": "ACME", "siren": ""}, ["siren"]),
            ({"name": "", "siren": "12345"}, ["name"]),
            ({"name": "ACME", "siren": "   "}, ["siren"]),
        ],
    )
    def test_individual_fields(self, form: dict[str, Any], expected: list[str]):
        assert content_form_missing_required(form) == expected

    def test_non_string_values_treated_as_missing(self):
        # The Flask form always returns strings, but a defensive contract
        # should treat unexpected types as missing rather than raise.
        assert content_form_missing_required({"name": None, "siren": 0}) == [
            "name",
            "siren",
        ]


# --- gallery_upload_outcome -----------------------------------------------


class TestGalleryUploadOutcome:
    """Decision branches of stage B1b's gallery upload handler."""

    MAX_IMG = 4 * 1024 * 1024

    def _call(self, **overrides: Any) -> str:
        defaults: dict[str, Any] = {
            "skip_add": False,
            "gallery_count": 0,
            "image_size": 1024,
            "max_gallery": 10,
            "max_image_size": self.MAX_IMG,
        }
        defaults.update(overrides)
        return gallery_upload_outcome(**defaults)

    def test_skip_add_routes_to_next_step(self):
        assert self._call(skip_add=True) == "redirect_next"

    def test_skip_add_wins_over_limit_reached(self):
        # skip_add must short-circuit even when the gallery is full.
        assert self._call(skip_add=True, gallery_count=99) == "redirect_next"

    @pytest.mark.parametrize("gallery_count", [10, 11, 50])
    def test_limit_reached_when_gallery_at_or_over_max(self, gallery_count: int):
        assert self._call(gallery_count=gallery_count) == "limit_reached"

    def test_no_image_when_image_size_none(self):
        assert self._call(image_size=None) == "no_image"

    @pytest.mark.parametrize("image_size", [MAX_IMG, MAX_IMG * 2, MAX_IMG * 5])
    def test_image_too_big_at_or_over_max(self, image_size: int):
        assert self._call(image_size=image_size) == "image_too_big"

    @pytest.mark.parametrize("image_size", [1, 1024, MAX_IMG - 1])
    def test_accept_when_within_limits(self, image_size: int):
        assert self._call(image_size=image_size) == "accept"

    def test_accept_at_gallery_count_below_max(self):
        assert self._call(gallery_count=9, image_size=2048) == "accept"


# --- gallery_swap_positions -----------------------------------------------


class TestGallerySwapPositions:
    """Up/down reorder semantics with boundary guards."""

    def _images(self) -> list[FakeGalleryImage]:
        return [
            FakeGalleryImage(id=10, position=0),
            FakeGalleryImage(id=20, position=1),
            FakeGalleryImage(id=30, position=2),
        ]

    def test_moves_middle_up(self):
        images = self._images()
        pair = gallery_swap_positions(images=images, target_id=20, direction="up")
        assert pair is not None
        target, neighbour = pair
        assert target.id == 20
        assert neighbour.id == 10

    def test_moves_middle_down(self):
        images = self._images()
        pair = gallery_swap_positions(images=images, target_id=20, direction="down")
        assert pair is not None
        target, neighbour = pair
        assert target.id == 20
        assert neighbour.id == 30

    def test_first_cannot_move_up(self):
        images = self._images()
        assert (
            gallery_swap_positions(images=images, target_id=10, direction="up") is None
        )

    def test_last_cannot_move_down(self):
        images = self._images()
        assert (
            gallery_swap_positions(images=images, target_id=30, direction="down")
            is None
        )

    def test_unknown_target_returns_none(self):
        images = self._images()
        assert (
            gallery_swap_positions(images=images, target_id=999, direction="up") is None
        )

    @pytest.mark.parametrize("direction", ["", "left", "sideways", "UP", "Down"])
    def test_unknown_direction_returns_none(self, direction: str):
        images = self._images()
        assert (
            gallery_swap_positions(images=images, target_id=20, direction=direction)
            is None
        )

    def test_empty_list_returns_none(self):
        assert gallery_swap_positions(images=[], target_id=1, direction="up") is None

    def test_swap_pair_preserves_positions_attribute(self):
        """The route swaps the two ``position`` fields after the helper
        returns the pair. Verifying the pair carries `position`
        protects the swap contract."""
        images = self._images()
        pair = gallery_swap_positions(images=images, target_id=20, direction="up")
        assert pair is not None
        first, second = pair
        # Carry the original positions so the route's swap is meaningful.
        assert first.position == 1
        assert second.position == 0
