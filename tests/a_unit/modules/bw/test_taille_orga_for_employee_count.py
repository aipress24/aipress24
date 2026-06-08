# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Ticket #0182 — pre-select the « Taille de l'organisation » dropdown
in stage B01 from the employee count typed during pricing."""

from __future__ import annotations

import pytest

from app.modules.bw.bw_activation.config import taille_orga_for_employee_count


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
