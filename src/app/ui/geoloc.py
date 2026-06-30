# Copyright (c) 2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Jinja filter rendering an offer's geoloc as a single human label.

Reads the structured KYC pair (`pays_zip_ville`, `pays_zip_ville_detail`)
when present, and falls back to the legacy free-text `location` for
records that pre-date the migration.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from app.modules.kyc.field_label import (
    country_code_to_label,
    country_zip_code_to_city,
)


def offer_geoloc_label(
    obj: Any,
    *,
    _country_resolver: Callable[[str], str] = country_code_to_label,
    _city_resolver: Callable[[str], str] = country_zip_code_to_city,
) -> str:
    # `_country_resolver` / `_city_resolver` are injectable ontology
    # lookups — production passes the real ones (the defaults) ; tests
    # pass stubs so they can exercise the formatting logic without an app
    # context or ontology data.
    pays = (getattr(obj, "pays_zip_ville", "") or "").strip()
    detail = (getattr(obj, "pays_zip_ville_detail", "") or "").strip()
    if pays:
        country = _country_resolver(pays)
        city = _city_resolver(detail) if detail else ""
        if country and city:
            return f"{city}, {country}"
        if country:
            return country
        if city:
            return city
    return (getattr(obj, "location", "") or "").strip()
