# Copyright (c) 2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Unit tests for the offer_geoloc Jinja filter (#0021 phase 5)."""

from __future__ import annotations

from dataclasses import dataclass

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
        label = offer_geoloc_label(
            offer,
            _country_resolver=lambda _c: "France",
            _city_resolver=lambda _d: "75001 Paris",
        )
        assert label == "75001 Paris, France"

    def test_only_country_set_yields_country_alone(self) -> None:
        offer = _FakeOffer(pays_zip_ville="FRA")
        label = offer_geoloc_label(offer, _country_resolver=lambda _c: "France")
        assert label == "France"

    def test_unknown_country_falls_through_to_legacy(self) -> None:
        offer = _FakeOffer(pays_zip_ville="???", location="Brest")
        # Helpers return empty: no structured label, fall back to location.
        label = offer_geoloc_label(
            offer,
            _country_resolver=lambda _c: "",
            _city_resolver=lambda _d: "",
        )
        assert label == "Brest"


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
