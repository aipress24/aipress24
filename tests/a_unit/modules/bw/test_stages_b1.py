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
into pure functions (``cancel_subscription_action``,
``parse_content_form``, ``content_form_missing_required``,
``gallery_upload_outcome``, ``gallery_swap_positions``). These tests
exercise those decisions with plain dicts and stand-in BW / subscription
objects — no Flask, no DB, no test doubles, no fixture patching.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest

from app.modules.bw.bw_activation.routes.stage_b1 import (
    cancel_subscription_action,
    content_form_missing_required,
    parse_content_form,
)
from app.modules.bw.bw_activation.routes.stage_b1b import (
    gallery_swap_positions,
    gallery_upload_outcome,
)

# --- Stand-in objects (Pattern C: real-fake collaborator) -----------------


@dataclass
class FakeSubscription:
    """Minimal stand-in for a Stripe-backed Subscription row.

    Only carries the single attribute the decision predicate reads.
    """

    stripe_customer_id: str | None = None


@dataclass
class FakeBW:
    """Minimal stand-in for a BusinessWall used by the cancel-subscription
    predicate. Carries only the attributes actually inspected."""

    subscription: FakeSubscription | None = None


@dataclass
class FakeGalleryImage:
    """Stand-in for `BWImage` used by gallery-swap tests."""

    id: int
    position: int = 0


# --- cancel_subscription_action -------------------------------------------


class TestCancelSubscriptionAction:
    """Branch coverage of the paid-BW cancellation decision tree."""

    def _bw(self, customer_id: str | None = None) -> FakeBW:
        return FakeBW(subscription=FakeSubscription(stripe_customer_id=customer_id))

    def test_redirects_to_stripe_portal_when_live_and_has_stripe_sub(self):
        action = cancel_subscription_action(
            bw_activated=True,
            business_wall=self._bw("cus_123"),
            user_id=1,
            manager_ids={1},
            stripe_live_enabled=True,
        )
        assert action == "redirect_stripe_portal"

    def test_no_stripe_portal_when_live_but_no_customer_id(self):
        """A BW created before Stripe was enabled still cancels locally."""
        action = cancel_subscription_action(
            bw_activated=True,
            business_wall=self._bw(customer_id=None),
            user_id=1,
            manager_ids={1},
            stripe_live_enabled=True,
        )
        assert action == "cancel_locally"

    @pytest.mark.parametrize(
        ("subscription", "stripe_live"),
        [
            (None, True),  # No subscription row at all
            (FakeSubscription(stripe_customer_id=None), True),  # Pre-Stripe BW
            (FakeSubscription(stripe_customer_id="cus_x"), False),  # Live disabled
        ],
    )
    def test_falls_back_to_local_cancel_outside_stripe_branch(
        self, subscription: FakeSubscription | None, stripe_live: bool
    ):
        action = cancel_subscription_action(
            bw_activated=True,
            business_wall=FakeBW(subscription=subscription),
            user_id=1,
            manager_ids={1},
            stripe_live_enabled=stripe_live,
        )
        assert action == "cancel_locally"

    def test_redirect_index_when_session_not_activated(self):
        action = cancel_subscription_action(
            bw_activated=False,
            business_wall=self._bw(),
            user_id=1,
            manager_ids={1},
            stripe_live_enabled=False,
        )
        assert action == "redirect_index"

    def test_not_authorized_when_bw_missing(self):
        action = cancel_subscription_action(
            bw_activated=True,
            business_wall=None,
            user_id=1,
            manager_ids={1},
            stripe_live_enabled=False,
        )
        assert action == "redirect_not_authorized_bw_not_found"

    def test_not_authorized_when_user_not_a_manager(self):
        action = cancel_subscription_action(
            bw_activated=True,
            business_wall=self._bw(),
            user_id=42,
            manager_ids={1, 7, 99},
            stripe_live_enabled=False,
        )
        assert action == "redirect_not_authorized_not_manager"

    def test_not_authorized_when_user_id_is_none(self):
        action = cancel_subscription_action(
            bw_activated=True,
            business_wall=self._bw(),
            user_id=None,
            manager_ids={1},
            stripe_live_enabled=False,
        )
        assert action == "redirect_not_authorized_not_manager"

    def test_stripe_branch_takes_priority_over_session_check(self):
        """Even if the session somehow lost ``bw_activated``, the Stripe
        portal branch must still win when applicable — otherwise we'd
        bounce a paying customer to ``/index`` and never tell Stripe."""
        action = cancel_subscription_action(
            bw_activated=False,
            business_wall=self._bw("cus_xyz"),
            user_id=1,
            manager_ids={1},
            stripe_live_enabled=True,
        )
        assert action == "redirect_stripe_portal"

    def test_happy_path_local_cancel(self):
        action = cancel_subscription_action(
            bw_activated=True,
            business_wall=self._bw(),
            user_id=7,
            manager_ids={7, 8, 9},
            stripe_live_enabled=False,
        )
        assert action == "cancel_locally"


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
            ({"name": "  ", "siren": "12345"}, ["name"]),  # whitespace-only counts as missing
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


# --- parse_content_form ----------------------------------------------------


class TestParseContentFormScalars:
    """Each ``if value: business_wall.field = value`` arm in the route."""

    @pytest.mark.parametrize(
        "key",
        [
            "name",
            "logo_image_copyright",
            "cover_image_copyright",
            "name_group",
            "siren",
            "tva",
            "agrement",
            "name_official",
            "positionnement_editorial",
            "audience_cible",
            "periodicite",
            "tel_standard",
            "postal_address",
            "geolocalisation",
            "site_url",
            "taille_orga",
            "clients",
            "name_institution",
        ],
    )
    def test_passes_through_truthy_scalar(self, key: str):
        out = parse_content_form({key: "value"})
        assert out == {key: "value"}

    def test_strips_whitespace(self):
        out = parse_content_form({"name": "  trimmed  ", "siren": "  9 "})
        assert out["name"] == "trimmed"
        assert out["siren"] == "9"

    @pytest.mark.parametrize("value", ["", "   ", "\n\t"])
    def test_drops_empty_scalar(self, value: str):
        # Empty / whitespace-only values are dropped, matching the
        # route's ``if value:`` guards.
        assert parse_content_form({"name": value}) == {}

    def test_returns_empty_dict_for_empty_form(self):
        assert parse_content_form({}) == {}

    def test_unknown_fields_are_ignored(self):
        out = parse_content_form({"unknown_field": "ignored", "name": "ACME"})
        assert out == {"name": "ACME"}


class TestParseContentFormTypeOrganisation:
    """``type_organisation`` is a single value wrapped in a list, with
    a sibling ``_detail`` multi-list."""

    def test_wraps_value_in_list(self):
        out = parse_content_form({"type_organisation": "MEDIA"})
        assert out["type_organisation"] == ["MEDIA"]
        # When _detail is absent, the route writes ``[]`` — matched here.
        assert out["type_organisation_detail"] == []

    def test_includes_detail_list_alongside_primary(self):
        out = parse_content_form(
            {"type_organisation": "MEDIA", "type_organisation_detail": ["a", "b"]}
        )
        assert out["type_organisation"] == ["MEDIA"]
        assert out["type_organisation_detail"] == ["a", "b"]

    def test_dropped_when_primary_empty(self):
        # No primary → no detail, even when detail is provided. Mirrors
        # the route's structure (the whole pair is gated on primary).
        out = parse_content_form(
            {"type_organisation": "", "type_organisation_detail": ["a", "b"]}
        )
        assert "type_organisation" not in out
        assert "type_organisation_detail" not in out


class TestParseContentFormMultiSelects:
    """Single multi-selects: keep the list if non-empty."""

    @pytest.mark.parametrize(
        "key",
        ["type_entreprise_media", "type_presse_et_media", "type_agence_rp"],
    )
    def test_pass_through_non_empty(self, key: str):
        out = parse_content_form({key: ["x", "y"]})
        assert out == {key: ["x", "y"]}

    @pytest.mark.parametrize(
        "key",
        ["type_entreprise_media", "type_presse_et_media", "type_agence_rp"],
    )
    def test_drop_empty(self, key: str):
        assert parse_content_form({key: []}) == {}


class TestParseContentFormDualSelects:
    """Dual multi-selects pair a primary list with a ``_detail`` list."""

    @pytest.mark.parametrize(
        ("primary", "detail"),
        [
            ("secteurs_activite", "secteurs_activite_detail"),
            ("interest_political", "interest_political_detail"),
            ("interest_economics", "interest_economics_detail"),
            ("interest_association", "interest_association_detail"),
        ],
    )
    def test_keeps_both_when_primary_non_empty(self, primary: str, detail: str):
        out = parse_content_form({primary: ["P1"], detail: ["D1", "D2"]})
        assert out[primary] == ["P1"]
        assert out[detail] == ["D1", "D2"]

    @pytest.mark.parametrize(
        ("primary", "detail"),
        [
            ("secteurs_activite", "secteurs_activite_detail"),
            ("interest_political", "interest_political_detail"),
            ("interest_economics", "interest_economics_detail"),
            ("interest_association", "interest_association_detail"),
        ],
    )
    def test_keeps_primary_with_empty_detail(self, primary: str, detail: str):
        out = parse_content_form({primary: ["P1"]})
        assert out[primary] == ["P1"]
        # Mirrors the route's ``or []`` fallback.
        assert out[detail] == []

    def test_drops_both_when_primary_empty(self):
        out = parse_content_form(
            {"secteurs_activite": [], "secteurs_activite_detail": ["D1"]}
        )
        assert "secteurs_activite" not in out
        assert "secteurs_activite_detail" not in out


class TestParseContentFormPaysZipVille:
    """``pays_zip_ville`` carries an extra string detail (not a list)."""

    @pytest.mark.parametrize(
        ("form", "expected"),
        [
            (
                {"pays_zip_ville": "FR", "pays_zip_ville_detail": "75001 Paris"},
                {"pays_zip_ville": "FR", "pays_zip_ville_detail": "75001 Paris"},
            ),
            (
                {"pays_zip_ville": "FR"},
                {"pays_zip_ville": "FR", "pays_zip_ville_detail": ""},
            ),
            (
                {"pays_zip_ville_detail": "75001 Paris"},
                {},  # No primary → no detail.
            ),
        ],
    )
    def test_pays_zip_ville_projection(
        self, form: dict[str, Any], expected: dict[str, Any]
    ):
        assert parse_content_form(form) == expected


class TestParseContentFormFullPayload:
    """End-to-end: a realistic media-tier payload survives the projection."""

    def test_typical_media_payload(self):
        form = {
            "name": "ACME Press",
            "siren": "123456789",
            "tva": "FR123",
            "name_official": "ACME Press SAS",
            "type_organisation": "MEDIA",
            "type_organisation_detail": ["online"],
            "type_entreprise_media": ["radio", "tv"],
            "secteurs_activite": ["tech"],
            "secteurs_activite_detail": ["ai", "robotics"],
            "pays_zip_ville": "FR",
            "pays_zip_ville_detail": "75001 Paris",
            "site_url": "https://example.com",
            "unknown": "noise",
        }
        out = parse_content_form(form)
        assert out["name"] == "ACME Press"
        assert out["siren"] == "123456789"
        assert out["type_organisation"] == ["MEDIA"]
        assert out["type_organisation_detail"] == ["online"]
        assert out["type_entreprise_media"] == ["radio", "tv"]
        assert out["secteurs_activite"] == ["tech"]
        assert out["secteurs_activite_detail"] == ["ai", "robotics"]
        assert out["pays_zip_ville"] == "FR"
        assert out["pays_zip_ville_detail"] == "75001 Paris"
        assert "unknown" not in out


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
            gallery_swap_positions(images=images, target_id=999, direction="up")
            is None
        )

    @pytest.mark.parametrize("direction", ["", "left", "sideways", "UP", "Down"])
    def test_unknown_direction_returns_none(self, direction: str):
        images = self._images()
        assert (
            gallery_swap_positions(images=images, target_id=20, direction=direction)
            is None
        )

    def test_empty_list_returns_none(self):
        assert (
            gallery_swap_positions(images=[], target_id=1, direction="up") is None
        )

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
