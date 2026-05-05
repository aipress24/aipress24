# Copyright (c) 2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Unit tests for the offer_geoloc Jinja filter (#0021 phase 5)."""

from __future__ import annotations

from dataclasses import dataclass
from unittest.mock import patch

from app.ui.geoloc import offer_geoloc_label


@dataclass
class _FakeOffer:
    pays_zip_ville: str = ""
    pays_zip_ville_detail: str = ""
    location: str = ""


class TestStructuredCases:
    def test_country_and_city_yields_combined_label(self) -> None:
        offer = _FakeOffer(
            pays_zip_ville="FRA",
            pays_zip_ville_detail="FRA / 75001 Paris",
        )
        with patch("app.ui.geoloc.country_code_to_label", return_value="France"), patch(
            "app.ui.geoloc.country_zip_code_to_city", return_value="75001 Paris"
        ):
            assert offer_geoloc_label(offer) == "75001 Paris, France"

    def test_only_country_set_yields_country_alone(self) -> None:
        offer = _FakeOffer(pays_zip_ville="FRA")
        with patch("app.ui.geoloc.country_code_to_label", return_value="France"):
            assert offer_geoloc_label(offer) == "France"

    def test_unknown_country_falls_through_to_legacy(self) -> None:
        offer = _FakeOffer(pays_zip_ville="???", location="Brest")
        with patch("app.ui.geoloc.country_code_to_label", return_value=""), patch(
            "app.ui.geoloc.country_zip_code_to_city", return_value=""
        ):
            # Helpers return empty: no structured label, fall back to location.
            assert offer_geoloc_label(offer) == "Brest"


class TestLegacyFallback:
    def test_only_legacy_location(self) -> None:
        offer = _FakeOffer(location="Lille — télétravail OK")
        assert offer_geoloc_label(offer) == "Lille — télétravail OK"

    def test_nothing_set_returns_empty(self) -> None:
        assert offer_geoloc_label(_FakeOffer()) == ""

    def test_strips_whitespace_only_strings(self) -> None:
        offer = _FakeOffer(location="   ")
        assert offer_geoloc_label(offer) == ""


class TestRobustness:
    def test_object_without_geoloc_attrs(self) -> None:
        class _Minimal:
            pass

        # Should not raise even when the object lacks geoloc fields entirely.
        assert offer_geoloc_label(_Minimal()) == ""

    def test_none_values_are_handled(self) -> None:
        offer = _FakeOffer(pays_zip_ville=None, location=None)  # type: ignore[arg-type]
        assert offer_geoloc_label(offer) == ""
