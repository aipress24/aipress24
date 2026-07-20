# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Ticket #0182 — pre-select the « Taille de l'organisation » dropdown
in stage B01 from the employee count typed during pricing."""

from __future__ import annotations

import pytest

from app.modules.bw.bw_activation.config import (
    employee_count_from_taille_orga,
    taille_orga_for_employee_count,
)


class TestTailleOrgaForEmployeeCount:
    @pytest.mark.parametrize(
        ("count", "expected"),
        [
            (1, "TPE"),
            (5, "TPE"),
            (9, "TPE"),
            (10, "PME"),
            (50, "PME"),
            (249, "PME"),
            (250, "ETI"),
            (1000, "ETI"),
            (4999, "ETI"),
            (5000, "GE"),
            (50_000, "GE"),
        ],
    )
    def test_maps_count_to_insee_bracket(self, count: int, expected: str):
        assert taille_orga_for_employee_count(count) == expected

    @pytest.mark.parametrize("count", [None, 0, -1, -100])
    def test_returns_empty_string_for_missing_or_invalid_count(self, count: int | None):
        """When no useful count is available, return "" so the dropdown
        in B01 stays empty and the user picks explicitly (including
        « Solo » which is not in the auto-mapping)."""
        assert taille_orga_for_employee_count(count) == ""


class TestEmployeeCountFromTailleOrga:
    """Bug 0255: the activation « Nombre de salariés » field now posts a
    `taille_organisation` bucket value; it must convert back to a
    representative employee count for the Stripe quantity / pricing tier."""

    @pytest.mark.parametrize(
        ("value", "expected"),
        [
            ("1", 1),
            ("10", 10),
            ("250", 250),
            ("1000000", 1_000_000),
            ("+", 1_000_000),
        ],
    )
    def test_maps_bucket_to_count(self, value: str, expected: int):
        assert employee_count_from_taille_orga(value) == expected

    @pytest.mark.parametrize("value", ["", None, "abc"])
    def test_returns_zero_for_empty_or_invalid(self, value: str | None):
        assert employee_count_from_taille_orga(value) == 0
