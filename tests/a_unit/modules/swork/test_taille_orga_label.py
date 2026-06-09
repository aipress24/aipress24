# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Unit tests for `_taille_orga_label` in
`app.modules.swork.components.members_list`.

`_taille_orga_label` maps a `taille_orga` ontology code to its
human-readable French label for the « Tailles d'organisation »
filter on /swork/members. The mapping :

- `"+"` → `« Plus de 1 000 000 »` (the « very large » bucket)
- `"1"` → `« 1 personne »` (singular, no « jusqu'à »)
- numeric value `"N"` → `« Jusqu'à N »`
- non-numeric / unrecognised → passed through verbatim

Pin so a future translation regression doesn't silently render
non-French labels in the directory filter.
"""

from __future__ import annotations

from app.modules.swork.components.members_list import _taille_orga_label


class TestTailleOrgaLabel:
    def test_plus_marker_returns_large_bucket_label(self):
        """The `« + »` ontology code marks the « very large org »
        bucket. Pin the French label and number formatting."""
        result = _taille_orga_label("+")
        assert result == "Plus de 1 000 000"

    def test_single_person_uses_singular_label(self):
        """`"1"` gets a SINGULAR « 1 personne » — not « Jusqu'à 1 »
        which would be grammatically weird. Pin so a future
        « collapse to numeric branch » regression breaks this nice
        UX detail."""
        result = _taille_orga_label("1")
        assert result == "1 personne"

    def test_typical_numeric_value(self):
        result = _taille_orga_label("10")
        assert result == "Jusqu’à 10"

    def test_uses_typographic_apostrophe(self):
        """The French label uses U+2019 (typographic apostrophe).
        Pin so a future regex replace doesn't accidentally swap it
        for the ASCII `'` and break the visual consistency."""
        result = _taille_orga_label("10")
        assert "’" in result
        assert result == "Jusqu’à 10"

    def test_large_numeric_value(self):
        """Pin so a future addition of thousands-separator
        formatting on the numeric branch is a conscious choice."""
        result = _taille_orga_label("1000")
        assert result == "Jusqu’à 1000"

    def test_non_numeric_passes_through(self):
        """The ValueError branch : returns the raw value so an
        unknown code at least renders SOMETHING. Pin so a future
        « fall back to empty » regression doesn't silently empty
        out user-supplied filter values."""
        result = _taille_orga_label("ETI")
        assert result == "ETI"

    def test_empty_string_passes_through(self):
        """`int("")` raises ValueError → fall-through path returns
        the empty string verbatim. Pin so a future tightening that
        returns `""` from the numeric branch is a conscious choice."""
        assert _taille_orga_label("") == ""

    def test_zero_treated_as_numeric(self):
        """`"0"` is a valid int → numeric branch fires → `« Jusqu'à 0 »`.
        Quirky but documents the actual behaviour ; pin so a refactor
        that special-cases zero is conscious."""
        assert _taille_orga_label("0") == "Jusqu’à 0"

    def test_negative_numeric(self):
        """`int("-1")` works → numeric branch. Defensive : pin so
        a refactor that filters non-positive doesn't silently break."""
        assert _taille_orga_label("-1") == "Jusqu’à -1"

    def test_decimal_string_returns_raw(self):
        """`int("3.14")` raises ValueError → fall-through. Pin so
        a future float-aware branch doesn't silently change the
        output shape."""
        assert _taille_orga_label("3.14") == "3.14"

    def test_returns_string(self):
        """The template renders the result directly ; pin the type
        so a stray int (`f"… {n}"` collapsed to int by accident)
        doesn't break the template."""
        for value in ("+", "1", "10", "bogus", ""):
            result = _taille_orga_label(value)
            assert isinstance(result, str)

    def test_two_specific_codes_are_distinguishable(self):
        """`"+"` and `"1"` produce different labels — they're the
        two special-cased values. Pin the disjoint output."""
        assert _taille_orga_label("+") != _taille_orga_label("1")
        # And neither equals the numeric-branch output for the
        # underlying number.
        assert _taille_orga_label("1") != _taille_orga_label("2")
