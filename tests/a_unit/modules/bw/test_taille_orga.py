# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Unit tests for `taille_orga_for_employee_count` in
`app.modules.bw.bw_activation.config`.

The KYC ontology key `taille_organisation` carries four canonical
size codes : `TPE` / `PME` / `ETI` / `GE`. The bracket table maps
an organisation's employee count to one of those codes ; the helper
is consulted when an admin imports a fresh org from an external
source and we need to pre-fill the size dropdown.

The contract is :
- 1 – 9     → TPE   (très petite entreprise)
- 10 – 249  → PME
- 250 – 4999 → ETI
- 5000+     → GE   (grande entreprise)
- 0 / None  → ""    (« no opinion » — the dropdown stays empty so
                    the user can pick `Solo` explicitly if applicable)

Pin the boundaries — getting one off by one would silently mislabel
every org at the bracket edges, with no error and no easy way for
the admin to spot the mistake afterwards.
"""

from __future__ import annotations

import pytest

from app.modules.bw.bw_activation.config import taille_orga_for_employee_count


class TestNoneAndZeroPolicy:
    """The « no opinion » return : empty string. The dropdown shows
    no selection so the user must explicitly pick the size."""

    def test_none_returns_empty(self):
        assert taille_orga_for_employee_count(None) == ""

    def test_zero_returns_empty(self):
        """Zero employees is a definitional edge case (e.g. a not-
        yet-staffed shell company). Treat as « no opinion » rather
        than mislabel as TPE."""
        assert taille_orga_for_employee_count(0) == ""

    def test_negative_returns_empty(self):
        """Defensive : negative employee counts are nonsense. Pin
        the empty-return so a crafted import doesn't silently land
        with a bogus default."""
        assert taille_orga_for_employee_count(-1) == ""
        assert taille_orga_for_employee_count(-1000) == ""


class TestTpeBracket:
    """1 – 9 employees → TPE."""

    @pytest.mark.parametrize("count", [1, 2, 5, 8, 9])
    def test_in_bracket(self, count):
        assert taille_orga_for_employee_count(count) == "TPE"

    def test_lower_boundary(self):
        """A single employee is TPE — pin the inclusive lower edge."""
        assert taille_orga_for_employee_count(1) == "TPE"

    def test_upper_boundary(self):
        """9 is TPE (inclusive). 10 escapes the bracket."""
        assert taille_orga_for_employee_count(9) == "TPE"
        assert taille_orga_for_employee_count(10) != "TPE"


class TestPmeBracket:
    """10 – 249 employees → PME."""

    @pytest.mark.parametrize("count", [10, 50, 100, 200, 249])
    def test_in_bracket(self, count):
        assert taille_orga_for_employee_count(count) == "PME"

    def test_lower_boundary(self):
        """10 is the first PME count (one over the TPE ceiling)."""
        assert taille_orga_for_employee_count(10) == "PME"

    def test_upper_boundary(self):
        """249 is PME ; 250 jumps to ETI."""
        assert taille_orga_for_employee_count(249) == "PME"
        assert taille_orga_for_employee_count(250) != "PME"


class TestEtiBracket:
    """250 – 4 999 employees → ETI."""

    @pytest.mark.parametrize("count", [250, 500, 1000, 2500, 4999])
    def test_in_bracket(self, count):
        assert taille_orga_for_employee_count(count) == "ETI"

    def test_lower_boundary(self):
        assert taille_orga_for_employee_count(250) == "ETI"

    def test_upper_boundary(self):
        """4999 is ETI ; 5000 jumps to GE. Pin both sides — the
        ETI/GE boundary trips up French regulators too, so we want
        a hard test."""
        assert taille_orga_for_employee_count(4999) == "ETI"
        assert taille_orga_for_employee_count(5000) == "GE"


class TestGeBracket:
    """5000+ employees → GE. No upper bound."""

    @pytest.mark.parametrize("count", [5000, 10_000, 100_000, 1_000_000])
    def test_in_bracket(self, count):
        assert taille_orga_for_employee_count(count) == "GE"

    def test_lower_boundary(self):
        assert taille_orga_for_employee_count(5000) == "GE"

    def test_extreme_count_still_works(self):
        """Sanity : an unrealistic org size (a billion employees)
        still resolves to GE rather than overflowing or returning
        empty."""
        assert taille_orga_for_employee_count(1_000_000_000) == "GE"


class TestReturnTypeAndStability:
    def test_always_returns_string(self):
        """Pin the return type — a future int-return regression would
        crash the ontology lookup downstream with a type error rather
        than just rendering wrong."""
        for count in (None, 0, 1, 50, 500, 5000):
            assert isinstance(taille_orga_for_employee_count(count), str)

    def test_returns_one_of_canonical_codes_or_empty(self):
        """The downstream KYC ontology only knows TPE/PME/ETI/GE/""."
        Anything else is a silent bug."""
        valid = {"", "TPE", "PME", "ETI", "GE"}
        for count in (None, -5, 0, 1, 9, 10, 249, 250, 4999, 5000, 100_000):
            assert taille_orga_for_employee_count(count) in valid

    @pytest.mark.parametrize(
        ("count", "expected"),
        [
            (None, ""),
            (0, ""),
            (1, "TPE"),
            (9, "TPE"),
            (10, "PME"),
            (249, "PME"),
            (250, "ETI"),
            (4999, "ETI"),
            (5000, "GE"),
            (50_000, "GE"),
        ],
    )
    def test_canonical_table(self, count, expected):
        """One parametrised cross-check that pins the full bracket
        table at once — easiest to update if the brackets ever
        change (only one place)."""
        assert taille_orga_for_employee_count(count) == expected
